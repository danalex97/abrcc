import { logging } from '../common/logger';


const logger = logging('Intercept');


export function makeHeader(quality) {
    return `HEADER${quality}`;
}


class UrlProcessor {
    constructor(_max_rates, _url) {
        this.max_rates = _max_rates;
        let url = `${_url}`;
        for (let prefix of ['http://', 'https://']) {
            if (url.includes(prefix)) {
                url = url.split(prefix)[1];
            }
        }
        this.url = url;
    }

    get quality() {
        try {
            return this.max_rates - parseInt(this.url.split('/')[1].split('video')[1]) + 1;
        } catch(err) {
            return undefined;
        }
    }

    get index() {
        try {
            return parseInt(this.url.split('/')[2].split('.')[0]);
        } catch(err) {
            return undefined;
        }
    }
}


export class InterceptorUtil {
    makeWritable(object, property, writable) {
        let descriptor = Object.getOwnPropertyDescriptor(object, property) || {};
        descriptor.writable = writable;
        Object.defineProperty(object, property, descriptor);
    }

    executeCallback(callback, event) {
        try {
            if (callback) {
                if (event) {
                    callback(event);
                } else {
                    callback();
                }
            }
        } catch(ex) {
            logger.log('Exception in', ex, callback);
        }
    }

    newEvent(ctx, type, dict) {
        let event = new ProgressEvent(type, dict);
        
        this.makeWritable(event, 'currentTarget', true);
        this.makeWritable(event, 'srcElement', true);
        this.makeWritable(event, 'target', true);
        this.makeWritable(event, 'trusted', true);
        
        event.currentTarget = ctx;
        event.srcElement = ctx;
        event.target = ctx;
        event.trusted = true;

        return event;
    }
}


export class Interceptor extends InterceptorUtil {
    constructor(videoInfo) {
        super();

        this._videoInfo = videoInfo;

        this._onRequest = (ctx, index) => {};
        
        // map of contexts for onIntercept
        this._toIntercept = {};

        // map of callbacks for onIntercept
        this._onIntercept = {};
        
        // map of done requests
        // the retries will not be requested, but only logged
        this._done = {};
    }
   
    onRequest(callback) {
        this._onRequest = callback;
        return this;
    }

    onIntercept(index, callback) {
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
    
    intercept(index) {
        this._toIntercept[index] = null;
        return this;
    }
    
    start() {
        let interceptor = this;
        let oldOpen = window.XMLHttpRequest.prototype.open;
        let max_rates = interceptor._videoInfo.bitrates.length;

        // override the open method
        function newXHROpen(method, url, async, user, password) {
            let ctx = this;
            let oldSend = this.send;

            // modify url
            if (url.includes('video') && url.endsWith('.m4s') && !url.includes('Header')) {
                let processor = new UrlProcessor(max_rates, url);
                let index = processor.index;
                
                if (interceptor._done[index] === undefined) {
                    interceptor._onRequest(ctx, index);
                    interceptor._done[index] = url;
                } else {
                    logger.log("Retry on request", index, url);
                }
            }
            ctx.send = function() {
                if (url.includes('video') && url.endsWith('.m4s')) {
                    let processor = new UrlProcessor(max_rates, url);
                    let index = processor.index;
                    let quality = processor.quality; 
                    
                    if (url.includes('init')) {
                        index = makeHeader(max_rates - quality + 1); 
                    }
    
                    if (interceptor._toIntercept[index] !== undefined) {
                        logger.log("intercepted", url);

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
                } else {
                    return oldSend.apply(this, arguments);
                }
            };
 
            return oldOpen.apply(this, arguments); 
        }

        window.XMLHttpRequest.prototype.open = newXHROpen;
    }
}


