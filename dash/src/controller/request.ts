import { logging, exportLogs } from '../common/logger';
import { VideoInfo } from '../common/video';
import { BackendShim, Request } from '../component/backend';
import { Dict } from '../types';


const logger = logging('RequestController');


type ResourceSendCallback = (index: number, url: string, content: string | undefined) => void;
type ResourceSendAfterCallback = (index: number, req: XMLHttpRequest) => void;
type ResourceOnAbortCallback = (index: number, req: XMLHttpRequest) => void;
type ResourceProgressCallback = (index: number, event: Event) => void;
type ResourceSuccessCallback = (index: number, res: XMLHttpRequest) => void;
type PieceSuccessCallback = (index: number, body: Body) => void; 


export class RequestController {
    _current: number;
    _pool: number;
    _shim: BackendShim;
    _index: number;
    _max_index: number;

    _resourceSend: ResourceSendCallback;
    _resourceAfterSend: ResourceSendAfterCallback;
    _resourceOnAbort: ResourceOnAbortCallback;
    _resourceProgress: ResourceProgressCallback;
    _resourceSuccess: ResourceSuccessCallback;
    _pieceSuccess: PieceSuccessCallback; 
    _pieceRequests: Dict<number, Request>; 
    _resourceRequests: Dict<number, Request>;

    constructor(videoInfo: VideoInfo, shim: BackendShim, pool: number) {
        this._current = 0;
        this._pool = pool;
        this._shim = shim;
        this._index = 0;
        
        this._resourceSend = (index, url, content) => {};
        this._resourceProgress = (index, event) => {}; 
        this._resourceSuccess = (index, res) => {};
        this._pieceSuccess = (index, body) => {};

        this._pieceRequests = {};
        this._resourceRequests = {};
        this._max_index = videoInfo.info[videoInfo.bitrateArray[0]].length;
    }

    getPieceRequest(index: number): Request {
        return this._pieceRequests[index];
    }

    getResourceRequest(index: number): Request {
        return this._resourceRequests[index];
    }

    _pieceRequest(index: number): void {
        this._pieceRequests[index] = this._shim
            .pieceRequest()
            .addIndex(index)
            .onSuccess((body) => {
                this._pieceSuccess(index, body);
            }).onFail(() => {
                throw new Error(`Piece request ${index} failed`)
            }).send();
    }

    _resourceRequest(index: number): void {
        this._resourceRequests[index] = this._shim
            .resourceRequest();
        
        this._resourceRequests[index]
            .addIndex(index)
            .onSend((url, content) => {
                this._resourceSend(index, url, content);    
            })
            .afterSend((request) => {
                this._resourceAfterSend(index, request);
            })
            .onProgress((event) => {
                this._resourceProgress(index, event);
            })
            .onAbort((request) => {
                this._resourceOnAbort(index, request);
            })
            .onSuccessResponse((res) => {    
                this._resourceSuccess(index, res);
            
                this._current -= 1;
                this._request();
            }).onFail(() => {
                throw new Error(`Resource request ${index} failed`)
            }).send();
    }

    _request(): void {
        logger.log("indexes", this._index, this._max_index);

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

    start(): RequestController {
        this._request();
        return this;
    }

    onResourceSend(callback: ResourceSendCallback): RequestController {
        this._resourceSend = callback;
        return this;
    }

    afterResourceSend(callback: ResourceSendAfterCallback): RequestController {
        this._resourceAfterSend = callback;
        return this;
    }

    onResourceAbort(callback: ResourceOnAbortCallback): RequestController {
        this._resourceOnAbort = callback;
        return this;
    }

    onResourceProgress(callback: ResourceProgressCallback): RequestController {
        this._resourceProgress = callback;
        return this;
    }

    onResourceSuccess(callback: ResourceSuccessCallback): RequestController {
        this._resourceSuccess = callback;
        return this;
    }

    onPieceSuccess(callback: PieceSuccessCallback): RequestController {
        this._pieceSuccess = callback;
        return this;
    }
}
