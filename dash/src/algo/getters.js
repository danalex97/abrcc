import { MetricGetter } from '../algo/interface';
import { Value } from '../common/data';
import { logging } from '../common/logger';
import { timestamp } from '../common/time';


const logger = logging('Getters');


export class RebufferTimeGetter extends MetricGetter {
    constructor() {
        super();
        this.smallestPlayerTime = null;
        this.biggestPlayerTime = new Value(0).withTimestamp(0);
    }

    update(metrics) {
        for (let playerTime of metrics.playerTime) {
            if (this.smallestPlayerTime === null) {
                this.smallestPlayerTime = playerTime;
            } else if (this.smallestPlayerTime.timestamp > playerTime.timestamp) {
                this.smallestPlayerTime = playerTime;
            }

            if (this.biggestPlayerTime.timestamp < playerTime.timestamp) {
                this.biggestPlayerTime = playerTime;
            }
        }
    }

    get value() {
        if (this.smallestPlayerTime !== null) {
            let ts_diff = this.biggestPlayerTime.timestamp - this.smallestPlayerTime.timestamp;
            let value_diff = this.biggestPlayerTime.value - this.smallestPlayerTime.value;
            
            return ts_diff - value_diff;
        }
        return 0;
    }
}


export class BufferLevelGetter extends MetricGetter {
    constructor() {
        super();
        this.lastBufferLevel = new Value(0).withTimestamp(0);
    }

    update(metrics) {
        this.lastBufferLevel = metrics.bufferLevel.reduce(
            (a, b) => a.timestamp < b.timestamp ? b : a, this.lastBufferLevel);
    }

    get value() {
        let value_at_timestmap = this.lastBufferLevel.value;    
        let consumed = timestamp(new Date()) - this.lastBufferLevel.timestamp;
        return value_at_timestmap - consumed;
    }
}


export class ThrpGetter extends MetricGetter {
    constructor() {
        super();

        this.segments = { 1 : {timestamp: 0} };
        this.lastSegment = 0;
        this.requests = {};
    
        this.horizon = 5;
    }

    update(metrics, ctx) {
        for (let segment of metrics.segments) {
            if (this.segments[segment.index] === undefined) {
                this.segments[segment.index] = segment;
            }
            if (segment.index > this.lastSegment) {
                this.lastSegment = segment.index;
            }
        }
        this.requests = ctx.requests;
    }
}


export class ThrpPredictorGetter extends ThrpGetter {
    get value() {
        if (this.lastSegment < 2) {
            return 0;
        }

        let totalSum = 0;
        let totalTime = 0;
        let minIndex = Math.max(this.lastSegment - this.horizon + 1, 2);
        for (let index = this.lastSegment; index >= minIndex; --index) {
            let time = this.segments[index].timestamp - this.segments[index - 1].timestamp;
            let size = this.requests[index - 2].response.byteLength * 8;

            totalSum += time * time / size;
            totalTime += time;
        }
        return totalTime / totalSum;
    }
}


export class LastThrpGetter extends ThrpGetter {
    get value() {
        if (this.lastSegment < 2) {
            return 0;
        }

        let index = this.lastSegment;

        let time = this.segments[index].timestamp - this.segments[index - 1].timestamp;    
        let size = this.requests[index - 2].response.byteLength * 8;
        return size / time;
    }
}

export class LastFetchTimeGetter extends ThrpGetter {
    get value() {
        if (this.lastSegment < 2) {
            return 0;
        }
        let index = this.lastSegment;
        let time = this.segments[index].timestamp - this.segments[index - 1].timestamp;    
        return time;
    }
}
