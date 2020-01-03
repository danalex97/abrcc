import { Metrics } from '../component/stats';
import { logging } from '../common/logger'; 


const logger = logging('StatsController');


export class StatsController {
    constructor() {
        this._metrics = new Metrics();
    }
    
    // Discard all information before timestamp, inclusively. 
    // @param {int} timestamp front-end generated
    advance(timestamp) {    
        let filter = (value) => value.timestamp > timestamp;
        this._metrics = new Metrics().withMetrics(this._metrics, filter);
    }
   
    // Get all metrics until the timestamp, inclusively.
    // @returns {Metrics} 
    // @param {int} timestamp front-end generated
    getMetrics(timestamp) {
        if (timestamp === undefined) {
            return new Metrics().withMetrics(this._metrics).sorted();
        } else {
            let filter = (value) => value.timestamp <= timestamp;
            return new Metrics().withMetrics(this._metrics, filter).sorted();
        }
    }

    get metrics() {
        return this.getMetrics();
    }

    addMetrics(metrics) {
        this._metrics.withMetrics(metrics);
    }
}
