import * as request from 'request';
import { logging } from '../common/logger'; 


const logger = logging('BackendShim');


export class Request {
    constructor(shim) {
        this._shim = shim;
        this._json = {
            'pieceRequest' : false,
        };
        this._callback = (body) => {};
        this._error = () => {};
    }

    addStats(stats) {
        this._json['stats'] = stats;
        return this;
    }

    addPieceRequest() {
        this._json['pieceRequest'] = true;
        return this;
    }

    send() {
        logger.log('sending request', this._json);
        request.post(this._shim.path, {
            json : this._json,
        }, (error, res, body) => {
            if (error) {
                logger.log(error);
                this._error();
                return
            }
            let statusCode = res.statusCode;
            if (statusCode != 200) {
                logger.log(`status code ${statusCode}`, res, body);
                this._error();
                return
            }
            logger.log('successful request', body);
            this._callback(body);
        })
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


export class BackendShim {
    constructor() {
        this._path = "https://www.example.org/request";
    }

    request() {
        return new Request(this);
    }

    get path() {
        return this._path;
    }
}
