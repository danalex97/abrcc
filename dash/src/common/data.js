import { timestamp as create_timestamp } from '../common/time';


const MAX_QUALITY = 5; // 0 -> 5
export const SEGMENT_STATE = {
    'DOWNLOADED': 'downloaded',
    'PROGRESS': 'progress',
    'LOADING': 'loading',
};


// @abstract
export class Piece {
    get index() {
        throw new TypeError("not implemented error")
    }

    get quality() {
        throw new TypeError("not implemented error")
    }

    get timestamp() {
        throw new TypeError("not implemented error")
    }
}


export class Value {
    constructor(value) {
        this._value = value;
        this._timestamp = create_timestamp(new Date());
    }

    withTimestamp(timestamp) {
        this._timestamp = timestamp;
        return this;
    }

    get value() {
        return this._value;
    }

    get timestamp() {
        return this._timestamp;
    }

    serialize() {
        return {
            "value" : this.value,
            "timestamp" : this.timestamp,
        };
    }
}


export class Decision extends Piece {
    constructor(index, quality, timestamp) {
        super();
        this._index = index;
        this._quality = quality;
        this._timestamp = timestamp;
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

export class Segment extends Piece {
    constructor() {
        super()
        this._timestamp = create_timestamp(new Date());
    }

    withLoaded(loaded) {
        this._loaded = loaded;
        return this;
    }

    withTotal(total) {
        this._total = total;
        return this;
    }

    withTimestamp(timestamp) {
        this._timestamp = timestamp;
        return this;
    }

    withQuality(quality) {
        this._quality = quality;
        return this;
    }

    withState(state) {
        this._state = state;
        return this;
    }

    withIndex(index) {
        this._index = index;
        return this;
    }
   
    withStartTime(startTime, duration) {
        // segments start from 1
        this._index = Math.round(startTime / duration) + 1;
        return this;
    }

    get total() {
        return this._total;
    }

    get loaded() {
        return this._loaded;
    }

    get timestamp() {
        return this._timestamp;
    }

    get index() {
        return this._index;
    }

    get quality() {
        return this._quality;
    }

    get state() { 
        return this._state;
    }

    serialize() {
        // We don't export the quality since the backend knows what decision it took
        if (this.state == SEGMENT_STATE.LOADING || this.state == SEGMENT_STATE.DOWNLOADED) {
            return {
                "index" : this.index,
                "state" : this.state,
                "timestamp" : this.timestamp,
            };
        } else if (this.state == SEGMENT_STATE.PROGRESS) {
            return {
                "index" : this.index,
                "state" : this.state,
                "timestamp" : this.timestamp,
                "loaded" : this.loaded,
                "total" : this.total,
            };
        } else {
            throw new RangeError(`Unrecognized segment state ${this.state}`);
        }
    }
}



