import * as request from 'request';
import { logging } from '../common/logger'; 


const logger = logging('BackendShim');


class Request {
    constructor(shim) {
        this._shim = shim;
        this._onBody = (body) => {};
        this._onResponse = (response) => {};
        this._error = () => {};
    }

    _nativeGet(path, resource, responseType) {
        logger.log('sending native GET request', path + resource);
        
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
        
        xhr.send();
    }

    _request(requestFunc, path, resource, content) {
        logger.log('sending request', path + resource, content);
        requestFunc(path + resource, content, (error, res, body) => {
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
            logger.log('successful request');
            this._onBody(body);
            this._onResponse(res);
        });
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
        this._path = "https://www.example.org/request";
        this._resource_path = "https://www.example.org/piece";    
    }

    metricsRequest() {
        return new MetricsRequest(this);
    }

    pieceRequest() {
        return new PieceRequest(this); 
    }

    resourceRequest() {
        return new ResourceRequest(this);
    }

    get resourcePath() {
        return this._resource_path;
    }

    get path() {
        return this._path;
    }
}
