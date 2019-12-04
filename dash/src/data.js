const MAX_QUALITY = 5;


export class Piece {
    get index() {
        throw new TypeError("not implemented error")
    }

    get timestamp() {
        throw new TypeError("not implemented error")
    }
}


export class Value {
    constructor(value, timestamp) {
        this.value = value;
        this.timestamp = new Date().getTime();
    }

    withTimestamp(timestamp) {
        this.timestamp = timestamp;
        return this;
    }
}


export class Segment extends Piece {
    constructor() {
        super()
        this.timestamp = new Date().getTime();
    }

    withTimestamp(timestamp) {
        this.timestamp = timestamp;
        return this;
    }

    withQuality(quality) {
        this.quality = quality;
        return this;
    }

    withState(state) {
        this.state = state;
        return this;
    }
   
    withIndex(startTime, duration) {
        this.index = Math.round(startTime / duration) - 1;
        return this;
    }

    // assumes format [domain]/video[quality]/[segment].[type]
    withUrl(url) {
        let split = url.split('/');
        
        let raw_quality = split[split.length - 2];
        let quality = parseInt(raw_quality.substring(5), 10); 
        
        let raw_segment = split[split.length - 1];
        let segment = parseInt(raw_segment.split('.')[0], 10);
    
        this.quality = MAX_QUALITY - quality + 1;
        this.index = segment;
        this.state = 'downloaded';
        
        return this;
    }
}



