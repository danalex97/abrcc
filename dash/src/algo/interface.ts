import { Metrics } from '../component/stats';
import { Request } from '../component/backend';
import { Decision } from '../common/data';


export abstract class AbrAlgorithm {
    requests: Array<XMLHttpRequest>; 
    
    constructor() {
        this.requests = [];
    }

    abstract getDecision(metrics: Metrics, index: number, timestamp: number): Decision;

    newRequest(ctx: XMLHttpRequest): void {
        this.requests.push(ctx);
    }
}

export abstract class MetricGetter {
    abstract update(metrics: Metrics, requests?: Array<XMLHttpRequest>): void;
    abstract get value(): number;
}
