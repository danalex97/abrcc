import { Metrics } from '../component/stats';
import { logging } from '../common/logger'; 


const logger = logging('StatsController');


export class StatsController {
    _metrics: Metrics;
    
    constructor() {
        this._metrics = new Metrics();
    }
    
    // Discard all information before timestamp, inclusively. 
    advance(timestamp: number): void {    
        let filter = (value) => value.timestamp > timestamp;
        this._metrics = new Metrics().withMetrics(this._metrics, filter);
    }
   
    // Get all metrics until the timestamp, inclusively.
    getMetrics(timestamp?: number): Metrics {
        if (timestamp === undefined) {
            return new Metrics().withMetrics(this._metrics).sorted();
        } else {
            let filter = (value) => value.timestamp <= timestamp;
            return new Metrics().withMetrics(this._metrics, filter).sorted();
        }
    }

    get metrics(): Metrics {
        return this.getMetrics();
    }

    addMetrics(metrics: Metrics): void {
        this._metrics.withMetrics(metrics);
    }
}
