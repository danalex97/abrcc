import { Metrics } from '../component/stats';
import { Request } from '../component/backend';
import { Decision } from '../common/data';

/**
 * AbrAlgorithm interface
 */
export abstract class AbrAlgorithm {
    requests: Array<XMLHttpRequest>; 
    
    constructor() {
        this.requests = [];
    }

    /**
     * Given the newly received `metrics`, take a `Decision` for the current `index`.
     * The decision has to be `timestamp`ed.
     */
    abstract getDecision(metrics: Metrics, index: number, timestamp: number): Decision;

    newRequest(ctx: XMLHttpRequest): void {
        this.requests.push(ctx);
    }
}

/**
 * MetricGetter interface: can be used to implement a specific derivation of a particular metric
 * given the previous HTTP requests and front-end metrics.
 */
export abstract class MetricGetter {
    /**
     * Given the newly received `metrics` and, possibly, a list of previous `XMLHttpRequsts` 
     * made to the backend update the metrics.
     */
    abstract update(metrics: Metrics, requests?: Array<XMLHttpRequest>): void;

    /**
     * Compute the current metric's value.
     */
    abstract get value(): number;
}
