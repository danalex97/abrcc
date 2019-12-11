import * as request from 'request';
import { logging } from '../common/logger'; 


const logger = logging('BackendShim');


class Request {
    constructor(shim) {
        this._shim = shim;
        this._callback = (body) => {};
        this._error = () => {};
    }

    _request(requestFunc, resource, content) {
        logger.log('sending request', content);
        requestFunc(this._shim.path + resource, content, (error, res, body) => {
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
            this._callback(body);
        });
        return this;
    }

    onFail(callback) {
        this._error = callback;
        return this;
    }

    onSuccess(callback) {
        this._callback = callback;
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
        return this._request(request.post, "", {
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
        return this._request(request.get, "/" + this.index, {});
    }
}

export class BackendShim {
    constructor() {
        this._path = "https://www.example.org/request";
    }

    metricsRequest() {
        return new MetricsRequest(this);
    }

    pieceRequest() {
        return new PieceRequest(this); 
    }

    get path() {
        return this._path;
    }
}
