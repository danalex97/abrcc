import { JsonDict, Json } from '../types';

import * as request from 'request';
import * as retryrequest from 'requestretry';
import { logging } from '../common/logger'; 

const logger = logging('BackendShim');

type RequestFunction = (
    url: string | Json, 
    content: Json, 
    callback: (error: Error, res: request, body: Body) => void,
) => XMLHttpRequest;

/**
 * Request wrapper class.
 *
 * Exposes callbacks for each part of the lifecycle of a request:
 *  - for all request types: onSend, onFail, onSuccess(& onSuccessResponse)
 *  - for native requests: onProgress
 *  - for native GETS: afterSend, onAbort
 *
 * Exposes the underlying request's send function.
 *
 * For debugging, the log() function will enable automatic logging in the `BackendShim` log.
 */
export abstract class Request {
    request: XMLHttpRequest | undefined;

    _shim: BackendShim; 
    _onBody: (body: Body) => void;
    _onResponse: (res: XMLHttpRequest) => void;
    _error: () => void;
    _onSend: (url: string, content: Json | undefined) => void;
    _afterSend: (res: XMLHttpRequest) => void;
    _onAbort: (res: XMLHttpRequest) => void;
    _progress: (event: Event) => void;
    _log: boolean;

    constructor(shim: BackendShim) {
        this._shim = shim;
        this._onBody = (body) => {};
        this._onResponse = (request) => {};
        this._error = () => {};
        this._onSend = (url, content) => {};
        this._afterSend = (request) => {};
        this._onAbort = (request) => {};
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
        xhr.onabort = () => {
            this._onAbort(xhr);
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
        if (requestFunc === request.get || requestFunc === request.post) {
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
        } else if (requestFunc === retryrequest.post) {
            this.request = requestFunc(path + resource, {
                'uri': path + resource, 
                'method': 'POST',
                'json': content,
                'maxAttempts': 1,
                'retryDelay': 100000,
            }, (error, res, body) => {
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
        }
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
        // only works for native GET requests
        this._afterSend = callback;
        return this;
    }

    onAbort(callback: (request: XMLHttpRequest) => void): Request {
        // only works for native GET requests
        this._onAbort = callback;
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


/**
 * Metrics POST via the node `request` library.
 */
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

/**
 * Experimental setup repeated POST via the node `request` library that marks that the DASH player
 * started running.
 */
export class StartLoggingRequest extends Request {
    constructor(shim) {
        super(shim);
    }

    send(): Request {
        return this._request(retryrequest.post, this.shim.experimentPath, "/start", {
            'start' : true,
        });
    }
}

/**
 * Experimental setup native synchronous POST that requests a decision.
 *
 * To be used by `algo/remote`. 
 */
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


/**
 * Experimental setup repeated POST via the node `request` library that marks that can be used 
 * to send periodic statistic to the experimental pipeline for metrics computation.
 */
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
        return this._request(retryrequest.post, this.shim.experimentPath, "/metrics", {
            json: this._json,
        });
    }
}

/**
 * *Backend* GET via the node `request` library asking for a `Decision` for a particular `index`. 
 */
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


/**
 * *Backend* GET via the node `request` library asking to abort the request for an `index`. 
 */
export class AbortRequest extends PieceRequest {
    send(): Request {
        if (this.index === undefined) {
            throw new TypeError(`PieceRequest made without index: ${this}`); 
        }
        return this._request(request.get, this.shim.abortPath, "/" + this.index, {});
    }
}

/**
 * *Backend* native GET asking for the header of a quality track. 
 *
 * The backend will return a response in the form of an `arraybuffer`.
 */
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


/**
 * *Backend* native GET asking for a segment. 
 *
 * The backend will return a response in the form of an `arraybuffer`.
 */
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


/**
 * BackendShim that builds all possible request types enumerated above, that is:
 *  - HeaderRequest
 *  - MetricsRequest
 *  - FrontEndDecisionRequest
 *  - StartLoggingRequest
 *  - MetricsLoggingRequest
 *  - PieceRequest
 *  - ResourceRequest
 *  - AbortRequest
 *  
 */
export class BackendShim {
    _base_path: string;
    _path: string;
    _abort: string;
    _resource_path: string;
    _experiment_path: string;
    
    constructor(site: string, metrics_port: number, quic_port: number) {
        // the base path refers to the backend server
        this._base_path = `https://${site}:${quic_port}`;
        this._path = `https://${site}:${quic_port}/request`;
        this._abort = `https://${site}:${quic_port}/abort`;
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

    abortRequest(): AbortRequest {
        return new AbortRequest(this);
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

    get abortPath(): string {
        return this._abort;
    }

    get experimentPath(): string {
        return this._experiment_path;
    }   
}
