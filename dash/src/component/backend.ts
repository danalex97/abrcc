import { JsonDict, Json } from '../types';

import * as request from 'request';
import { logging } from '../common/logger'; 

const logger = logging('BackendBackendShim');

type RequestFunction = (
    url: string, 
    content: Json, 
    callback: (error: Error, res: request, body: Body) => void,
) => XMLHttpRequest;

export abstract class Request {
    request: XMLHttpRequest | undefined;

    _shim: BackendShim; 
    _onBody: (body: Body) => void;
    _onResponse: (res: XMLHttpRequest) => void;
    _error: () => void;
    _onSend: (url: string, content: Json | undefined) => void;
    _afterSend: (res: XMLHttpRequest) => void;
    _progress: (event: Event) => void;
    _log: boolean;

    constructor(shim: BackendShim) {
        this._shim = shim;
        this._onBody = (body) => {};
        this._onResponse = (request) => {};
        this._error = () => {};
        this._onSend = (url, content) => {};
        this._afterSend = (request) => {};
        this._progress = (event) => {}; 
        this._log = false;
        
        // underlying request object
        this.request = undefined;
    }

    _nativeSyncPost(path: string, resource: string, content: Json): Request {
        if (this._log) {
            logger.log('Sending native sync POST request', path + resource);
        }

        let xhr = new XMLHttpRequest();
        xhr.open("POST", path + resource, false);

        xhr.onreadystatechange = () => {
            if (xhr.readyState == 4 && xhr.status == 200) {
                this._onResponse(xhr);
            }
        };

        xhr.send(JSON.stringify(content));
        return this;
    }

    _nativeGet(
        path: string, 
        resource: string, 
        responseType: XMLHttpRequestResponseType,
    ): Request {
        if (this._log) {
            logger.log('Sending native GET request', path + resource);
        }

        let xhr = new XMLHttpRequest();
        logger.log('GET', path + resource);
        xhr.open('GET', path + resource);
        if (responseType !== undefined) {
            xhr.responseType = responseType;
        }
        
        xhr.onload = () => {
            if (xhr.status == 200) {
                this._onResponse(xhr);
            } else {
                this._error();
            }
        };
        xhr.onerror = () => {
            this._error(); 
        };
        xhr.onprogress = (event) => {
            this._progress(event);
        };

        this._onSend(path + resource, undefined);
        xhr.send();
        this._afterSend(xhr);
    
        this.request = xhr;
        return this;
    }

    _request(
        requestFunc: RequestFunction, 
        path: string, 
        resource: string, 
        content: Json,
     ): Request {
        if (this._log) {
            logger.log('sending request', path + resource, content);
        }
        this._onSend(path + resource, content);
        this.request = requestFunc(path + resource, content, (error, res, body) => {
            if (error) {
                logger.log(error);
                this._error();
                return;
            }
            let statusCode = res.statusCode;
            if (statusCode != 200) {
                logger.log(`status code ${statusCode}`, res, body);
                this._error();
                return;
            }
            if (this._log) {
                logger.log('successful request');
            }
            this._onBody(body);
            this._onResponse(res);
        });
        return this;
    }

    // Builder pattern methods below
    // -----------------------------
    onProgress(callback: (e: Event) => void): Request {
        // only works for native requests
        this._progress = callback;
        return this;
    }

    onSend(callback: (url: string, content: string | undefined) => void): Request {
        this._onSend = callback;
        return this;
    }

    
    afterSend(callback: (request: XMLHttpRequest) => void): Request {
        // only works for native requests
        this._afterSend = callback;
        return this;
    }

    onFail(callback: () => void): Request {
        this._error = callback;
        return this;
    }

    onSuccess(callback: (body: Body) => void): Request {
        this._onBody = callback;
        return this;
    }

    onSuccessResponse(callback: (res: XMLHttpRequest) => void): Request {
        this._onResponse = callback;
        return this;
    }

    log(): Request  {
        this._log = true;
        return this;
    }

    // Getters below
    // -------------
    get shim(): BackendShim {
        return this._shim;
    }

    // Abstract methods
    // ----------------
    abstract send(): Request;
}


export class MetricsRequest extends Request {
    _json: JsonDict; 
    
    constructor(shim) {
        super(shim);
        this._json = {
        };
    }

    addStats(stats: Json): MetricsRequest {
        this._json['stats'] = stats;
        return this;
    }

    send() {
        return this._request(request.post, this.shim.path, "", {
            json : this._json,
        });
    }
}


export class StartLoggingRequest extends Request {
    constructor(shim) {
        super(shim);
    }

    send(): Request {
        return this._request(request.post, this.shim.experimentPath, "/start", {
            'start' : true,
        });
    }
}


export class FrontEndDecisionRequest extends Request {
    _object: JsonDict;
    
    constructor(shim) {
        super(shim);
        
        this._object = {};
    }

    addLastFetchTime(time: number): FrontEndDecisionRequest {
        this._object['last_fetch_time'] = time;
        return this;
    }
    
    addIndex(index: number): FrontEndDecisionRequest {
        this._object['index'] = index;
        return this;
    }

    addBuffer(buffer: number): FrontEndDecisionRequest {
        this._object['buffer'] = buffer;
        return this;
    }

    addRebuffer(rebuffer: number): FrontEndDecisionRequest {
        this._object['rebuffer'] = rebuffer;
        return this;
    }
    
    addBandwidth(bandwidth: number): FrontEndDecisionRequest {
        this._object['bandwidth'] = bandwidth;
        return this;
    }

    send(): Request {
        return this._nativeSyncPost(this.shim.experimentPath, "/decision", this._object);
    }
}


export class MetricsLoggingRequest extends MetricsRequest {
    constructor(shim: BackendShim) {
        super(shim);
    }

    addLogs(logs: Array<string>): MetricsLoggingRequest {
        this._json['logs'] = logs;
        return this; 
    }

    addComplete(): MetricsLoggingRequest {
        this._json['complete'] = true;
        return this;
    }

    send(): Request {
        return this._request(request.post, this.shim.experimentPath, "/metrics", {
            json: this._json,
        });
    }
}


export class PieceRequest extends Request {
    index: number | undefined;

    constructor(shim: BackendShim) {
        super(shim);
    }

    addIndex(index: number): PieceRequest {
        this.index = index;
        return this;
    }
    
    send(): Request {
        if (this.index === undefined) {
            throw new TypeError(`PieceRequest made without index: ${this}`); 
        }
        return this._request(request.get, this.shim.path, "/" + this.index, {});
    }
}


export class HeaderRequest extends Request {
    quality: number | undefined;

    constructor(shim: BackendShim) {
        super(shim);
    }

    addQuality(quality: number): HeaderRequest {
        this.quality = quality;
        return this;
    }

    send(): Request {
        if (this.quality === undefined) {
            throw new TypeError(`HeaderRequest made without quality: ${this}`); 
        }
        let resource = `/video${this.quality}/init.mp4`;
        return this._nativeGet(this.shim.basePath, resource, "arraybuffer");
    }
}


export class ResourceRequest extends Request {
    index: number | undefined;
    
    constructor(shim: BackendShim) {
        super(shim);
    }

    addIndex(index: number): ResourceRequest {
        this.index = index;
        return this;
    }
    
    send(): Request {
        if (this.index === undefined) {
            throw new TypeError(`ResourceRequest made without index: ${this}`); 
        }
        return this._nativeGet(this.shim.resourcePath, "/" + this.index, "arraybuffer");
    }
}

export class BypassRequest extends ResourceRequest {
    quality: number | undefined;

    constructor(shim: BackendShim) {
        super(shim);
    }
    
    addQuality(quality: number): BypassRequest {
        this.quality = quality;
        return this;
    }

    url(): string {
        return `${this.shim.basePath}/video${this.quality}/${this.index}.m4s`;
    }

    send(): Request {
        return this._nativeGet(
            this.shim.basePath, 
            `/video${this.quality}/${this.index}.m4s`, 
            "arraybuffer"
        );
    }
}


export class BackendShim {
    _base_path: string;
    _path: string;
    _resource_path: string;
    _experiment_path: string;
    
    constructor(site: string, metrics_port: number, quic_port: number) {
        // the base path refers to the backend server
        this._base_path = `https://${site}:${quic_port}`;
        this._path = `https://${site}:${quic_port}/request`;
        this._resource_path = `https://${site}:${quic_port}/piece`;    

        // the experiment path is used as a logging and control service
        this._experiment_path = `https://${site}:${metrics_port}`;
    }

    headerRequest(): HeaderRequest {
        return new HeaderRequest(this);
    }

    metricsRequest(): MetricsRequest {
        return new MetricsRequest(this);
    }

    frontEndDecisionRequest(): FrontEndDecisionRequest {
        return new FrontEndDecisionRequest(this);
    }

    startLoggingRequest(): StartLoggingRequest {
        return new StartLoggingRequest(this);
    }

    metricsLoggingRequest(): MetricsLoggingRequest {
        return new MetricsLoggingRequest(this);
    }

    pieceRequest(): PieceRequest {
        return new PieceRequest(this); 
    }

    resourceRequest(): ResourceRequest {
        return new ResourceRequest(this);
    }

    bypassRequest(): BypassRequest {
        return new BypassRequest(this);
    }

    get basePath(): string {
        return this._base_path;
    }

    get resourcePath(): string {
        return this._resource_path;
    }

    get path(): string {
        return this._path;
    }

    get experimentPath(): string {
        return this._experiment_path;
    }   
}
