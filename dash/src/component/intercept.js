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
    }
   
    onRequest(callback) {
        this._onRequest = callback;
        return this;
    }
    
    start() {
         // make properties writable
         let makeWritable = (object, property) => {
            let descriptor = Object.getOwnPropertyDescriptor(object, property) || {};
            descriptor.writable = true;
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
                logger.log('Request', url);
                return oldSend.apply(this, arguments);
            };
            return oldOpen.apply(this, arguments); 
        }

        window.XMLHttpRequest.prototype.open = newXHROpen;
    }
}


