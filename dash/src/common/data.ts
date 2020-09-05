import { timestamp as create_timestamp } from '../common/time';


export interface SegmentState {
    readonly DOWNLOADED: string;
    readonly PROGRESS: string;
    readonly LOADING: string;
}


export const SEGMENT_STATE: SegmentState = {
    DOWNLOADED: 'downloaded',
    PROGRESS: 'progress',
    LOADING: 'loading',
};


export abstract class Piece {
    abstract get index(): number; 
    abstract get quality(): number;
    abstract get timestamp(): number;
}


/**
 * Timestamped real number.
 */
export class Value {
    _value: number;
    _timestamp: number;
    
    constructor(value: number) {
        this._value = value;
        this._timestamp = create_timestamp(new Date());
    }

    withTimestamp(timestamp: number): Value {
        this._timestamp = timestamp;
        return this;
    }

    get value(): number {
        return this._value;
    }

    get timestamp(): number {
        return this._timestamp;
    }

    serialize() {
        return {
            "value" : this.value,
            "timestamp" : this.timestamp,
        };
    }
}

/**
 * Data-representation for a decision taken based on metrics received until timestamp `timestamp`
 * for piece number `index` for downloading at quality `quality`. 
 */
export class Decision extends Piece {
    _index: number;
    _quality: number;
    _timestamp: number;
    
    constructor(index, quality, timestamp) {
        super();
        this._index = index;
        this._quality = quality;
        this._timestamp = timestamp;
    }
    
    get index(): number {
        return this._index; 
    }

    get quality(): number {
        return this._quality;
    }

    get timestamp(): number {
        return this._timestamp;   
    }
}

/**
 * Segment representation used for serialization in communication with the back-end and experiment 
 * coordinator. Contains both metadata(quality, index, state) related to the segment together with the 
 * state of the download process(`loaded` bytes out of `total`).
 *
 * Can be serialized via the `serialize` function.
 **/
export class Segment extends Piece {
    _timestamp: number;
    
    _quality: number; // quality value from 0 -> maxQuality - 1
    _index: number; // index value from 1 -> #segments
    _state: string; // state from [downloaded, progress, loading]
    
    _loaded: number; // loaded bits
    _total: number; // total size in bits

    constructor() {
        super()
        this._timestamp = create_timestamp(new Date());
    }

    withLoaded(loaded: number): Segment {
        this._loaded = loaded;
        return this;
    }

    withTotal(total: number): Segment {
        this._total = total;
        return this;
    }

    withTimestamp(timestamp: number): Segment {
        this._timestamp = timestamp;
        return this;
    }

    withQuality(quality: number): Segment {
        this._quality = quality;
        return this;
    }

    withState(state: string): Segment {
        this._state = state;
        return this;
    }

    withIndex(index: number): Segment {
        this._index = index;
        return this;
    }
   
    withStartTime(startTime, duration): Segment {
        // segments start from 1
        this._index = Math.round(startTime / duration) + 1;
        return this;
    }

    get total(): number {
        return this._total;
    }

    get loaded(): number {
        return this._loaded;
    }

    get timestamp(): number {
        return this._timestamp;
    }

    get index(): number {
        return this._index;
    }

    get quality(): number {
        return this._quality;
    }

    get state(): string { 
        return this._state;
    }

    /**
     * Serialize the segment. If the `full` value is set, the `quality` of the segment will be 
     * included in the JSON serialization.
     */
    serialize(full: boolean): object {
        let ret = {};
        if (this.state == SEGMENT_STATE.LOADING || this.state == SEGMENT_STATE.DOWNLOADED) {
            ret = {
                "index" : this.index,
                "state" : this.state,
                "timestamp" : this.timestamp,
            };
        } else if (this.state == SEGMENT_STATE.PROGRESS) {
            ret = {
                "index" : this.index,
                "state" : this.state,
                "timestamp" : this.timestamp,
                "loaded" : this.loaded,
                "total" : this.total,
            };
        } else {
            throw new RangeError(`Unrecognized segment state ${this.state}`);
        }
        if (full) {
            ret = Object.assign(ret, {
                "quality" : this.quality,
            });
        }
        return ret;
    }
}



