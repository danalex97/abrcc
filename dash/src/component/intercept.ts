import { Dict, ExternalDependency } from '../types';
import { logging, Logger } from '../common/logger';
import { VideoInfo } from '../common/video';

/**
 * WARNING: Here be dragons
 */

declare global {
    interface Window {
        XMLHttpRequest: ExternalDependency;
    }
}


const logger: Logger = logging('Intercept');


export function makeHeader(quality: number): string {
    return `HEADER${quality}`;
}


/**
 * UrlProcessor class that allows extration of `quality` and `index` from a default  XmlHTTP 
 * request made by DASH.
 */
class UrlProcessor {
    max_rates: number
    url: string

    constructor(_max_rates: number, _url: string) {
        this.max_rates = _max_rates;
        let url = `${_url}`;
        for (let prefix of ['http://', 'https://']) {
            if (url.includes(prefix)) {
                url = url.split(prefix)[1];
            }
        }
        this.url = url;
    }

    get quality(): number | undefined {
        try {
            return parseInt(this.url.split('/')[1].split('video')[1]);
        } catch(err) {
            return undefined;
        }
    }

    get index(): number | undefined {
        try {
            return parseInt(this.url.split('/')[2].split('.')[0]);
        } catch(err) {
            return undefined;
        }
    }
}


/**
 * Intercetor utility that can be used for modification of a XMLHttp object.
 */
export class InterceptorUtil {
    /**
     * Make an object propety writable or unwritable.
     */
    makeWritable(object: object, property: any, writable: any) {
        let descriptor = Object.getOwnPropertyDescriptor(object, property) || {};
        descriptor.writable = writable;
        Object.defineProperty(object, property, descriptor);
    }

    /**
     * For a given event, execute a callback on that event. To not crash the player, 
     * catch and log any errors in event execution.
     */ 
    executeCallback(
        callback: undefined | ((event: ProgressEvent | undefined) => void),
        event: ProgressEvent | undefined
    ): void {
        try {
            if (callback) {
                if (event) {
                    callback(event);
                } else {
                    callback(undefined);
                }
            }
        } catch(ex) {
            logger.log('Exception in', ex, callback);
        }
    }

    /**
     * For the XMLHttpRequest prototype, create a ProgressEvent of type `type` attached to the 
     * XMLHttpRequest with the modified attributes according to dictionary `dict`.
     *
     * Make the event undistiguishable from a native event for DASH.js my modifying the ProgressEvent's
     * default generated properties(currentTarget, srcElement, target and trusted). When the progress
     * event is delivered(i.e. XMLHttpRequest's onprogress called), DASH will see our custom event.
     */
    newEvent(ctx: ExternalDependency, type: any, dict: any): ProgressEvent {
        let event = new ProgressEvent(type, dict);

        this.makeWritable(event, 'currentTarget', true);
        this.makeWritable(event, 'srcElement', true);
        this.makeWritable(event, 'target', true);
        this.makeWritable(event, 'trusted', true);

        // @ts-ignore: read-only propoerty
        event.currentTarget = ctx;
        // @ts-ignore: read-only propoerty
        event.srcElement = ctx;
        // @ts-ignore: read-only propoerty
        event.target = ctx;
        // @ts-ignore: read-only propoerty
        event.trusted = true;

        return event;
    }
}


/**
 * Intercetor class that stops outgoing segment XMLHttpRequests made by DASH(matched by the URL structure)
 * and simulates progress and delivery events after the actual requests to the backend made via the 
 * BackendShim have finished.
 *
 * The class allows attaching various callbacks so that our DASH wrapper can interact directly with the 
 * backend.
 */
export class Interceptor extends InterceptorUtil {
    // Note we allow both number and string input, since we want to also be able to intercept
    // header, but also numbered requests to the backend.
    _videoInfo: VideoInfo;
    _onRequest: (ctx: ExternalDependency, index: number) => void;
    _toIntercept: Dict<number | string, Dict<string, object>>;
    _onIntercept: Dict<number | string, (context: Dict<string, object>) => void>;
    _objects: Dict<number | string, object>;
    _done: Dict<number, string>;
    _bypass: Set<number>;

    constructor(videoInfo: VideoInfo) {
        super();

        this._videoInfo = videoInfo;

        this._onRequest = (ctx, index) => {};

        // map of contexts for onIntercept
        this._toIntercept = {};

        // map of callbacks for onIntercept
        this._onIntercept = {};

        // map of exposed context inside intercetor request
        this._objects = {};

        // map of done requests
        // the retries will not be requested, but only logged
        this._done = {};

        // set of bypass requests
        this._bypass = new Set();
    }

    get videoLength(): number {
        return this._videoInfo.info[this._videoInfo.bitrateArray[0]].length;
    }

    /**
     * Allows for a *single* callback to be made for a particular `index` before the XMLHttpRequest 
     * is intercepted. The callback exposes our XMLHttpRequest prototype.
     */
    onRequest(callback: (ctx: ExternalDependency, index: number) => void): Interceptor {
        this._onRequest = callback;
        return this;
    }

    /**
     * Allow for a *single* callback to be made for a particular `index` as the send function 
     * is called for the intercepted request.
     */
    onIntercept(index: number | string, callback: (context: Dict<string, object>) => void): Interceptor {
        logger.log('Cache updated', index);
        this._onIntercept[index] = callback;

        // if we already have a context on toIntercept we can call
        // the function
        if (this._toIntercept[index] !== null && this._toIntercept[index] !== undefined) {
            let ctx = this._toIntercept[index].ctx;
            callback(this._toIntercept[index]);
        }

        return this;
    }

    /**
     * Trigger a progress event for segment `index` with `loaded` bytes out of `total` bytes.
     */
    progress(index: number, loaded: number, total: number): void {
        if (this._toIntercept[index] !== null) {
            const object = this._toIntercept[index];

            let ctx = object["ctx"];
            const makeWritable = object["makeWritable"];
            const execute = object["execute"];
            const newEvent = (type, dict) => {
                return object["newEvent"](ctx, type, dict);
            };

            // dispach the progress events towards the original request
            makeWritable(ctx, 'readyState', true);
            ctx.readyState = 3;
            execute(ctx.onprogress, newEvent('progress', {
                'lengthComputable': true,
                'loaded': loaded,
                'total': total,
            }));
        }
    }
    
    /**
     * Return the *context* for a request made at segment `index`:
     *   The context contains: 
     *    - ctx: the newXHROpen new prototype
     *    - url: the intercepted request url
     *    - makeWritable, execute, newEvent: attached InterceptorUtil functions
     */
    context(index: number | string): object {
        return this._objects[index];
    }

    /**
     * Set context for an `index`. Should be genrally called only by the intercetor itself.
     */
    setContext(index: number | string, obj: object): Interceptor {
        this._objects[index] = obj;
        return this;
    }

    /**
     * Set a bypass over the intercetor filter for single *index*. The bypass works only once. 
     *
     * This function will be used for request aborts.
     */
    setBypass(index: number): Interceptor {
        this._bypass.add(index);
        return this;
    }

    /**
     * Mark that the onIntercept function has been attached for an `index` and hence needs to be 
     * called later by the interceptor.
     */
    intercept(index: number | string): Interceptor {
        this._toIntercept[index] = null;
        return this;
    }

    /**
     * Start the interceptor. After the start function has been called, all the native outgoing XMLHttp 
     * requests constructed after this point will be put through the intercetor filter. 
     */
    start() {
        let interceptor = this;
        let oldOpen = window.XMLHttpRequest.prototype.open;
        let max_rates: number = interceptor._videoInfo.bitrates.length;

        // override the open method
        function newXHROpen(method, url, async, user, password) {
            let ctx = this;
            let oldSend = this.send;

            let bypassDetected = false;
            // modify url
            if (url.includes('video') && url.endsWith('.m4s') && !url.includes('Header')) {
                logger.log('To modify', url);

                let processor = new UrlProcessor(max_rates, url);
                let maybeIndex = processor.index;
                if (maybeIndex === undefined) {
                    logger.log(`[error] Index not present in ${url}`);
                } else {
                    let index = maybeIndex as number;
                    if (interceptor._done[index] === undefined) {
                        interceptor._onRequest(ctx, index);
                        interceptor._done[index] = url;
                    } else {
                        if (interceptor._bypass.has(index)) {
                            // Bypass detected
                            logger.log("Bypass detected", index, url);

                            bypassDetected = true;
                            interceptor._onRequest(ctx, index);
                            interceptor._done[index] = url;
                        } else {
                            logger.log("Retry on request", index, url);
                        }
                    }
                }
            }
            if (bypassDetected) {
                return oldOpen.apply(this, arguments);
            }

            ctx.send = function() {
                if (url.includes('video') && url.endsWith('.m4s')) {
                    logger.log(url);

                    let processor = new UrlProcessor(max_rates, url);
                    let maybeIndex = processor.index;
                    let quality = processor.quality;

                    if (maybeIndex === undefined) {
                        logger.log(`[error] Index not present in ${url}`);
                    } else {
                        let index = maybeIndex as number;
                        if (interceptor._toIntercept[index] !== undefined) {
                            logger.log("intercepted", url, ctx);

                            // adding the context
                            interceptor._toIntercept[index] = {
                                'ctx': ctx,
                                'url': url,

                                'makeWritable': interceptor.makeWritable,
                                'execute': interceptor.executeCallback,
                                'newEvent': interceptor.newEvent,
                            };

                            // if the callback was set this means we already got the new response
                            if (interceptor._onIntercept[index] !== undefined) {
                                interceptor._onIntercept[index](interceptor._toIntercept[index]);
                                return;
                            }
                            return;
                        } else {
                            return oldSend.apply(this, arguments);
                        }
                    }
                } else {
                    return oldSend.apply(this, arguments);
                }
            };

            return oldOpen.apply(this, arguments);
        }

        // @ts-ignore: overriding XMLHttpRequest
        window.XMLHttpRequest.prototype.open = newXHROpen;
    }
}
