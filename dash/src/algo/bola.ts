import { AbrAlgorithm } from '../algo/interface';
import { Decision } from '../common/data';
import { Metrics } from '../component/stats';


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
