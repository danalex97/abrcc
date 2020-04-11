import { logging, exportLogs } from '../common/logger';
import { BackendShim } from '../component/backend';


const logger = logging('RequestController');


export class RequestController {
    constructor(videoInfo, shim, pool) {
        this._current = 0;
        this._pool = pool;
        this._shim = shim;
        this._index = 0;
        
        this._resourceSend = (index, url, content) => {};
        this._resourceProgress = (index, event) => {}; 
        this._resourceSuccess = (index, res) => {};
        this._pieceSuccess = (index, body) => {};

        this._pieceRequests = {};
        this._max_index = videoInfo.bitrateArray.length;
    }

    getPieceRequest(index) {
        return this._pieceRequests[index];
    }

    _pieceRequest(index) {
        this._pieceRequests[index] = this._shim
            .pieceRequest()
            .addIndex(index)
            .onSuccess((body) => {
                this._pieceSuccess(index, body);
            }).onFail(() => {
                throw new Error(`Piece request ${index} failed`)
            }).send();
    }

    _resourceRequest(index) {
        this._shim
            .resourceRequest()
            .addIndex(index)
            .onSend((url, content) => {
                this._resourceSend(index, url, content);    
            })
            .onProgress((event) => {
                this._resourceProgress(index, event);
            })
            .onSuccessResponse((res) => {    
                this._resourceSuccess(index, res);
            
                this._current -= 1;
                this._request();
            }).onFail(() => {
                throw new Error(`Resource request ${index} failed`)
            }).send();
    }

    _request() {
        if (this._current < this._pool && this._index < this._max_index) {
            this._current += 1;
            this._index += 1;
        } else {
            return;
        }
        let index = this._index;

        this._pieceRequest(index);
        this._resourceRequest(index);
        
        this._request(); 
    }

    start() {
        this._request();
        return this;
    }

    onResourceSend(callback) {
        this._resourceSend = callback;
        return this;
    }

    onResourceProgress(callback) {
        this._resourceProgress = callback;
        return this;
    }

    onResourceSuccess(callback) {
        this._resourceSuccess = callback;
        return this;
    }

    onPieceSuccess(callback) {
        this._pieceSuccess = callback;
        return this;
    }
}
