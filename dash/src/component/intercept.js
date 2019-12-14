import { logging } from '../common/logger';


const logger = logging('Intercept');
const MAX_QUALITY = 6;


class UrlProcessor {
    constructor(_url) {
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
            return MAX_QUALITY - parseInt(this.url.split('/')[1].split('video')[1]) + 1;
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


export class Interceptor {
    constructor() {
        this._onRequest = (index) => {};
        
        // map of contexts for onIntercept
        this._toIntercept = {};
        
        // map of callbacks for onIntercept
        this._onIntercept = {};
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
            callback(this._toIntercept[index]);
        }

        return this;
    }
    
    intercept(index) {
        this._toIntercept[index] = null;
        return this;
    }

    start() {
         // make properties writable
         let makeWritable = (object, property, writable) => {
            let descriptor = Object.getOwnPropertyDescriptor(object, property) || {};
            descriptor.writable = writable;
            Object.defineProperty(object, property, descriptor);
         };

        let interceptor = this;
        let oldOpen = window.XMLHttpRequest.prototype.open; 

        // override the open method
        function newXHROpen(method, url, async, user, password) {
            let ctx = this;
            let oldSend = this.send;

            // modify url
            if (url.includes('video') && url.endsWith('.m4s') && !url.includes('Header')) {
                let processor = new UrlProcessor(url);
                interceptor._onRequest(processor.index);
            }

            ctx.send = function() {
                if (url.includes('video') && url.endsWith('.m4s') && !url.includes('Header')) {
                    let processor = new UrlProcessor(url);
                    let index = processor.index;
                    if (interceptor._toIntercept[index] !== undefined) {
                        logger.log("intercepted", url);

                        // adding the context
                        interceptor._toIntercept[index] = {
                            'ctx': ctx,
                            'url': url,
                            'makeWritable': makeWritable,
                        };

                        // if the callback was set this means we already got the new response
                        if (interceptor._onIntercept[index] !== undefined) {
                            interceptor._onIntercept[index](interceptor._toIntercept[index]);
                        }
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


