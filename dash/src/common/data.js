import { timestamp as create_timestamp } from '../common/time';


const MAX_QUALITY = 5; // 0 -> 5


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
        return {
            "index" : this.index,
            "quality" : this.quality,
            "state" : this.state,
            "timestamp" : this.timestamp,
        };
    }
}



