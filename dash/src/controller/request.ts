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


/**
 * Controller responsible for maintaining a fixed pool of long-polling requests.
 *
 * It contains 2 pools of requests(symetric to each other):
 *   - a pull of piece requests: high level-HTTP requests with JSON content
 *   - a pull of resource requests: XMLHttp native requests
 */
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

    /**
     * Getter for piece requests.
     */ 
    getPieceRequest(index: number): Request {
        return this._pieceRequests[index];
    }

    /**
     * Geter for resource requests.
     */
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

    /**
     * Starts the asynchrnous pool of requests. As both piece and resource requests finish for a piece
     * they get replaces with requests for the pieces with the next index.
     */
    start(): RequestController {
        this._request();
        return this;
    }

    /**
     * Allows attaching a *single* callback before sending a resource request. 
     */
    onResourceSend(callback: ResourceSendCallback): RequestController {
        this._resourceSend = callback;
        return this;
    }

    /**
     * Allows attaching a *single* callback after sending a resource request.
     */
    afterResourceSend(callback: ResourceSendAfterCallback): RequestController {
        this._resourceAfterSend = callback;
        return this;
    }

    /**
     * Allows attaching a *single* callback after a resource request was aborted.
     */
    onResourceAbort(callback: ResourceOnAbortCallback): RequestController {
        this._resourceOnAbort = callback;
        return this;
    }

    /**
     * Allows attaching a *single* callback after the browser dispache an update event 
     * on the XMLHttp request associated with a resource request.
     */
    onResourceProgress(callback: ResourceProgressCallback): RequestController {
        this._resourceProgress = callback;
        return this;
    }

    /** 
     * Allows attaching a *single* callback after the resource request has successfully 
     * finished. 
     */
    onResourceSuccess(callback: ResourceSuccessCallback): RequestController {
        this._resourceSuccess = callback;
        return this;
    }

    /**
     * Allows attaching a *single* callback before a piece request was made.
     */
    onPieceSuccess(callback: PieceSuccessCallback): RequestController {
        this._pieceSuccess = callback;
        return this;
    }
}
