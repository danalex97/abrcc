import * as request from 'request';
import { logging } from '../common/logger'; 


const logger = logging('BackendShim');


class Request {
    constructor(shim) {
        this._shim = shim;
        this._onBody = (body) => {};
        this._onResponse = (response) => {};
        this._error = () => {};
        this._onSend = (url, content) => {};
        this._progress = (event) => {}; 
        this._log = false;

        // underlying request object
        this.request = undefined;
    }

    _nativeGet(path, resource, responseType) {
        if (this._log) {
            logger.log('sending native GET request', path + resource);
        }

        let xhr = new XMLHttpRequest();
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
    
        this.request = xhr;
    }

    _request(requestFunc, path, resource, content) {
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

    onProgress(callback) {
        // only works for native requests
        this._progress = callback;
        return this;
    }

    onSend(callback) {
        this._onSend = callback;
        return this;
    }
    
    onFail(callback) {
        this._error = callback;
        return this;
    }

    onSuccess(callback) {
        this._onBody = callback;
        return this;
    }

    onSuccessResponse(callback) {
        this._onResponse = callback;
        return this;
    }

    get shim() {
        return this._shim;
    }

    log() {
        this._log = true;
        return this;
    }
}


export class MetricsRequest extends Request {
    constructor(shim) {
        super(shim);
        this._json = {
        };
    }

    addStats(stats) {
        this._json['stats'] = stats;
        return this;
    }

    send() {
        return this._request(request.post, this.shim.path, "", {
            json : this._json,
        });
    }
}


export class MetricsLoggingRequest extends MetricsRequest {
    constructor(shim) {
        super(shim);
    }

    send() {
        return this._request(request.post, this.shim.experimentPath, "/metrics", {
            json : this._json,
        });
    }
}


export class PieceRequest extends Request {
    constructor(shim) {
        super(shim);
    }

    addIndex(index) {
        this.index = index;
        return this;
    }
    
    send() {
        return this._request(request.get, this.shim.path, "/" + this.index, {});
    }
}


export class HeaderRequest extends Request {
    constructor(shim) {
        super(shim);
    }

    addQuality(quality) {
        this.quality = quality;
        return this;
    }

    send() {
        let resource = `/video${this.quality}/Header.m4s`;
        return this._nativeGet(this.shim.basePath, resource, "arraybuffer");
    }
}


export class ResourceRequest extends Request {
    constructor(shim) {
        super(shim);
    }

    addIndex(index) {
        this.index = index;
        return this;
    }
    
    send() {
        return this._nativeGet(this.shim.resourcePath, "/" + this.index, "arraybuffer");
    }
}


export class BackendShim {
    constructor() {
        // the base path refers to the backend server
        this._base_path = "https://www.example.org";
        this._path = "https://www.example.org/request";
        this._resource_path = "https://www.example.org/piece";    

        // the experiment path is used as a logging and control service
        this._experiment_path = "https://www.example.org:8080";
    }

    headerRequest() {
        return new HeaderRequest(this);
    }

    metricsRequest() {
        return new MetricsRequest(this);
    }

    metricsLoggingRequest() {
        return new MetricsLoggingRequest(this);
    }

    pieceRequest() {
        return new PieceRequest(this); 
    }

    resourceRequest() {
        return new ResourceRequest(this);
    }

    get basePath() {
        return this._base_path;
    }

    get resourcePath() {
        return this._resource_path;
    }

    get path() {
        return this._path;
    }

    get experimentPath() {
        return this._experiment_path;
    }   
}
