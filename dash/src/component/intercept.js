import { timestamp as create_timestamp } from '../common/time';

import { Piece } from '../common/data'; 
import { PieceCache } from '../common/cache';
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
        return MAX_QUALITY - parseInt(this.url.split('/')[1].split('video')[1]) + 1;
    }

    get index() {
        return parseInt(this.url.split('/')[2].split('.')[0]);
    }
}

export class DataPiece extends Piece {
    constructor(rawData) {
        super();

        let sep = '$$$$';
        let pos = rawData.indexOf(sep);

        let url = rawData.substring(0, pos);
        let data = rawData.substring(pos + sep.length);
        
        this._data = data;
        this._url = url;

        this._timestamp = create_timestamp(new Date());
        
        let processor = new UrlProcessor(url);
        this._quality = processor.quality;
        this._index = processor.index;
    }

    get data() {
        return new TextEncoder().encode(this._data);
    }
    
    get index() {
        return this._index;
    }

    get quality() {
        return this._quality;
    }

    get timestamp() {
        return this._timestamp;
    }
}



export class Interceptor extends PieceCache {
    constructor() {
        super(); 
    }

    start() { 
        // make properties writable
        let makeWritable = (object, property) => {
            let descriptor = Object.getOwnPropertyDescriptor(object, property) || {};
            descriptor.writable = true;
            Object.defineProperty(object, property, descriptor);
        };
        // makeWritable(window.XMLHttpRequest, 'responseUrl');
        // makeWritable(window.XMLHttpRequest, 'response');

        let interceptor = this;
        let oldOpen = window.XMLHttpRequest.prototype.open; 

        // override the open method
        function newXHROpen(method, url, async, user, password) {
            let ctx = this;
            let oldSend = ctx.send;
            
            ctx.send = () => {
                if (url.includes('video') && url.endsWith('.m4s') && !url.includes('Header')) {
                    logger.log('Intercepted', url);
                    // get the piece
                    let index = new UrlProcessor(url).index;
                    let piece = interceptor.piece(index);
                    if (piece == undefined) {
                        setTimeout(ctx.send, 1000);  
                        return;
                    }
                    logger.log('Cached piece', url, piece);

                    // make writable
                    makeWritable(ctx, 'responseURL');
                    makeWritable(ctx, 'response'); 
                    makeWritable(ctx, 'readyState');
                    makeWritable(ctx, 'status');
                    makeWritable(ctx, 'statusText');
                   
                    // starting
                    ctx.readyState = 3;
                    if (ctx.onreadystatechange) {
                        ctx.onreadystatechange();
                    }

                    // modify response
                    ctx.responseType = "arraybuffer";
                    ctx.responseURL = url;
                    ctx.response = piece.data;
                    ctx.readyState = 4;
                    ctx.status = 200;
                    ctx.statusText = "OK";
                    logger.log('Overrided', ctx);

                    // do callbacks
                    if (ctx.onreadystatechange) {
                        ctx.onreadystatechange();
                    }
                    if (ctx.onloadend) {
                        ctx.onloadend(); 
                    }
                    return oldSend.apply(this, arguments);
                } else {
                    logger.log('Pass', ctx);
                    return oldSend.apply(this, arguments);
                }
            };
            return oldOpen.apply(this, arguments);
        }

        window.XMLHttpRequest.prototype.open = newXHROpen;
    }
}


