import { AbrAlgorithm } from '../algo/interface';
import { Decision } from '../common/data';
import { Metrics } from '../component/stats';


/**
 * BOLA is a buffer-based algorithm provided by default in the DASH.js player. This AbrAlgorithm class
 * is, actually, just a placeholder class.
 */
export class Bola extends AbrAlgorithm {
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
