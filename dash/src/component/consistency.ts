import { Dict } from '../types';

import { Piece } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('PieceConsistencyChecker');
const STATS_INTERVAL = 20000;


class Stream {
    _callbacks: Array<(value: any) => void>; 

    constructor() {
        this._callbacks = [];
    }

    push(value: any): void {
        for (let callback of this._callbacks) {
            callback(value);
        }
    }

    onPush(callback: (value: any) => void): void {
        this._callbacks.push(callback); 
    }
}


class ConsistencyChecker {
    _streams: Dict<string, Stream>; 
    _values: Dict<string, any>; 

    constructor() {
        this._streams = {};
        this._values = {};
    
        setInterval(() => {
            this.__stats();
        }, STATS_INTERVAL);    
    }

    __stats(): void {
        logger.log("Periodic stats...");
        for (let name in this._streams) {
            let size = Object.keys(this._values[name] || {}).length;
            logger.log(`stream ${name}`, `size ${size}`, this._values[name]);
        }
    }

    __addStream(name: string, stream: Stream): void {
        this._streams[name] = stream;
        this._values[name] = {};

        stream.onPush((piece) => {
            if (!(piece instanceof Piece)) {
                throw new TypeError("[ConsistencyChecker] wrong type inserted")
            }
            this._values[name][piece.index] = piece.quality;
            for (let name2 in this._streams) {
                let q1 = this._values[name][piece.index];
                let q2 = this._values[name2][piece.index];
                if (q2 !== undefined && q1 !== q2) {
                    logger.log(`Inconsistent qualities for index ${piece.index}`, 
                        `${name}: ${q1}`, `${name2}: ${q2}`);
                }   
            }
        });
    }

    push(name: string, value: any): void {
        if (this._streams[name] === undefined) {
            this.__addStream(name, new Stream());
        }
        this._streams[name].push(value);
    }
}


const checker = new ConsistencyChecker();


class TargetedChecker {
    name: string;

    constructor(name: string) {
        this.name = name;
    }
    
    push(value: any): void {
        checker.push(this.name, value);
    }
}

export function checking(name: string): TargetedChecker {
    return new TargetedChecker(name);
}
