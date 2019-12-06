import { Piece } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('PieceConsistencyChecker');


class Stream {
    constructor() {
        this._callbacks = [];
    }

    push(value) {
        for (let callback of this._callbacks) {
            callback(value);
        }
    }

    onPush(callback) {
        this._callbacks.push(callback); 
    }
}


class ConsistencyChecker {
    constructor() {
        this._streams = {};
        this._values = {};
    }

    __addStream(name, stream) {
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

    push(name, value) {
        if (this._streams[name] === undefined) {
            this.__addStream(name, new Stream());
        }
        this._streams[name].push(value);
    }
}


const checker = new ConsistencyChecker();


class TargetedChecker {
    constructor(name) {
        this.name = name;
    }
    
    push(value) {
        checker.push(this.name, value);
    }
}

export function checking(name) {
    return new TargetedChecker(name);
}
