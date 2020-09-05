import { Metrics } from '../component/stats';
import { logging } from '../common/logger'; 


const logger = logging('StatsController');


/**
 * Single source of truth for all Metrics updates.
 */
export class StatsController {
    _metrics: Metrics;
    
    constructor() {
        this._metrics = new Metrics();
    }
    
    /**
     * Discard all information before timestamp, inclusively. 
     */
    advance(timestamp: number): void {    
        let filter = (value) => value.timestamp > timestamp;
        this._metrics = new Metrics().withMetrics(this._metrics, filter);
    }
   
    /**
     * Get all metrics until the timestamp, inclusively. If a timestamp was not 
     * provided, return all the metrics. The metrics are return in a new Metrics object.
     */
    getMetrics(timestamp?: number): Metrics {
        if (timestamp === undefined) {
            return new Metrics().withMetrics(this._metrics).sorted();
        } else {
            let filter = (value) => value.timestamp <= timestamp;
            return new Metrics().withMetrics(this._metrics, filter).sorted();
        }
    }

    /**
     * Return all the metrics.
     */
    get metrics(): Metrics {
        return this.getMetrics();
    }

    /**
     * Add a new Metrics object as an update over the current held metrics.
     */ 
    addMetrics(metrics: Metrics): void {
        this._metrics.withMetrics(metrics);
    }
}
