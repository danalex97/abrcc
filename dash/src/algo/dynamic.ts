import { AbrAlgorithm } from '../algo/interface';
import { Decision } from '../common/data';
import { Metrics } from '../component/stats';


/**
 * Dynamic is the default DASH.js algorithm. This AbrAlgorithm class is, actually, just a 
 * placeholder class.
 */
export class Dynamic extends AbrAlgorithm {
    constructor() {
        super();
    }
   
    getDecision(metrics: Metrics, index: number, timestamp: number): Decision {
        return new Decision(
            index,
            undefined,
            timestamp,
        );
    }
}
