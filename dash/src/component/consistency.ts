import { Dict } from '../types';

import { Piece } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('PieceConsistencyChecker');
const STATS_INTERVAL = 20000;


/** 
 * Stream that allows multiple callbacks after each push.
 */
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


/**
 * Automatic consistency check crass that accepts pushes to any number of streams and 
 * checks that the stream values are consistent. The stream classes allow replacements as we allow
 * for segment downloads to be canceled(via Aborts).
 */
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

    /**
     * Push `value` to stream `name`. 
     * 
     * After each push, the consistency will be automatically checked with the rest of streams 
     * and inconsistencies will be logged.
     */
    push(name: string, value: any): void {
        if (this._streams[name] === undefined) {
            this.__addStream(name, new Stream());
        }
        this._streams[name].push(value);
    }

    /**
     * Replace the `index` `value` from stream `name`.
     */
    replace(name: string, index: number, value: any): void {
        this._values[name][index] = value;
    }
}


const checker = new ConsistencyChecker();

/**
 * Checker targeted on stream `name`.
 */
class TargetedChecker {
    name: string;

    constructor(name: string) {
        this.name = name;
    }
    
    /**
     * Push a value to the stream.
     *
     * After each push, the consistency will be automatically checked with the rest of streams 
     * and inconsistencies will be logged.
     */
    push(value: any): void {
        checker.push(this.name, value);
    }

    /**
     * Replace a value from the steam.
     */
    replace(index: number, value: any): void {
        checker.replace(this.name, index, value); 
    }
}

/**
 * Returns a targetted checker.
 */
export function checking(name: string): TargetedChecker {
    return new TargetedChecker(name);
}
