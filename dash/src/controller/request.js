import { logging } from '../common/logger';
import { BackendShim } from '../component/backend';


const logger = logging('RequestControler');


// [TODO] Should we still use this?
export class RequestController {
    constructor(poolSize, shim) {
        this._currentSize = 0;
        this._poolSize = poolSize;
        this._shim = shim;
        this._index = 1;
        this._success = (index, body) => {};
    }

    _request() {
        if (this._currentSize < this._poolSize) {
            let index = this._index; 
            this._shim
                .pieceRequest()
                .addIndex(index)
                .onSuccess((body) => {
                    logger.log(`Piece downloaded successfully ${index}`);
                    this._success(index, body);
                    this._currentSize -= 1;
                    this._request();
                }).onFail(() => {
                    logger.log(`Failed to get piece ${index}`);
                }).send();
            this._index += 1;
            this._currentSize += 1;
        }
        return this._currentSize >= this._poolSize;
    }

    start() {
        while (!this._request());
        return this;
    }

    onSuccess(callback) {
        this._success = callback;
        return this;
    }
}
