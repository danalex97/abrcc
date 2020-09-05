import { MetricGetter } from '../algo/interface';
import { Metrics } from '../component/stats';
import { Request } from '../component/backend';
import { Value, Segment } from '../common/data';
import { logging } from '../common/logger';
import { timestamp } from '../common/time';
import { Dict } from '../types';


const logger = logging('Getters');
const defaultThrp = 0;


/**
 * Getter that computes the latest timestamped rebuffer time in ms.
 */
export class RebufferTimeGetter extends MetricGetter {
    smallestPlayerTime: null | Value;
    biggestPlayerTime: Value;
    
    constructor() {
        super();
        this.smallestPlayerTime = null;
        this.biggestPlayerTime = new Value(0).withTimestamp(0);
    }

    update(metrics: Metrics): void {
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

    get value(): number {
        if (this.smallestPlayerTime !== null) {
            let ts_diff = this.biggestPlayerTime.timestamp - this.smallestPlayerTime.timestamp;
            let value_diff = this.biggestPlayerTime.value - this.smallestPlayerTime.value;
            
            let value = ts_diff - value_diff;
            if (value < 0) {
                return 0;
            } else {
                return value;
            }
        }
        return 0;
    }
}


/**
 * Getter that computes the latest timestamped buffer level.
 */ 
export class BufferLevelGetter extends MetricGetter {
    lastBufferLevel: Value;
    
    constructor() {
        super();
        this.lastBufferLevel = new Value(0).withTimestamp(0);
    }

    update(metrics: Metrics): void {
        this.lastBufferLevel = metrics.bufferLevel.reduce(
            (a, b) => a.timestamp < b.timestamp ? b : a, this.lastBufferLevel);
    }

    get value(): number {
        let value_at_timestmap = this.lastBufferLevel.value;    
        let consumed = timestamp(new Date()) - this.lastBufferLevel.timestamp;
        return Math.max(value_at_timestmap - consumed, 0);
    }
}


/**
 * Abstract getter that computes:
 *  - requests: a list of all the XMLHttpRequests made so far
 *  - segments: a list containing the download state of all the Segments encoutered so far
 *  - lastSegment: the index of the latest segments for which a download was started
 *  - horizon: a horizon constant used by throuput-based estimators to be derived from this class
 */
export abstract class ThrpGetter extends MetricGetter {
    segments: Dict<number, Segment>;
    requests: Array<XMLHttpRequest>;
    lastSegment: number;
    horizon: number;

    constructor() {
        super();

        this.segments = { 1 : new Segment().withTimestamp(0) };
        this.requests = [];
        
        this.lastSegment = 0;
        this.horizon = 5;
    }

    update(metrics: Metrics, requests: Array<XMLHttpRequest>): void {
        for (let segment of metrics.segments) {
            if (this.segments[segment.index] === undefined) {
                this.segments[segment.index] = segment;
            }
            if (segment.index > this.lastSegment) {
                this.lastSegment = segment.index;
            }
        }
        this.requests = requests;
    }
}


/**
 * Throughput predictor that computes the throughput based on the harmonic mean of the observed 
 * throughput of the last segments in the horizon. The implementation coincides with the take on 
 * RobustMpc(https://users.ece.cmu.edu/~vsekar/papers/sigcomm15_mpcdash.pdf) as a baseline the 
 * repository: https://github.com/hongzimao/pensieve.
 */
export class ThrpPredictorGetter extends ThrpGetter {
    get value(): number {
        if (this.lastSegment < 2) {
            return 0;
        }

        let totalSum = 0;
        let totalTime = 0;
        let minIndex = Math.max(this.lastSegment - this.horizon + 1, 2);
        for (let index = this.lastSegment; index >= minIndex; --index) {
            let time = 0;
            // Race condition -- if we get no metrics, then we need to pass some defaultThrp
            // -- in this case we pass 0
            if (this.segments[index - 1] !== undefined) {
                time = this.segments[index].timestamp - this.segments[index - 1].timestamp;
            }
            let size = this.requests[index - 2].response.byteLength * 8;

            totalSum += time * time / size;
            totalTime += time;
        }

        if (totalSum == 0) {
            return defaultThrp;
        }
        return totalTime / totalSum;
    }
}

/**
 * Computes the throughput of the last segment.
 */
export class LastThrpGetter extends ThrpGetter {
    get value(): number {
        if (this.lastSegment < 2) {
            return 0;
        }

        let index = this.lastSegment;
        let time = 0;
        // Race condition -- if we get no metrics, then we need to pass some defaultThrp
        // -- in this case we pass 0
        if (this.segments[index - 1] !== undefined) {
            time = this.segments[index].timestamp - this.segments[index - 1].timestamp;
        }
        let size = this.requests[index - 2].response.byteLength * 8;

        if (time == 0) {
            return defaultThrp; 
        }
        return size / time;
    }
}

/**
 * Computes the diffrence between timestmaps for the start of download for the last 2 segments.
 */
export class LastFetchTimeGetter extends ThrpGetter {
    get value(): number {
        if (this.lastSegment < 2) {
            return 0;
        }
        let index = this.lastSegment;
        let time = 0;
        
        // Race condition -- if we get no metrics, then we need to pass 0
        if (this.segments[index - 1] !== undefined) {
            time = this.segments[index].timestamp - this.segments[index - 1].timestamp;
        }
        return time;
    }
}
