import { AbrAlgorithm } from '../algo/interface';
import { Decision } from '../common/data';


export class Bola extends AbrAlgorithm {
    constructor() {
        super();
    }
   
    getDecision(metrics, index, timestamp) {
        return new Decision(
            index,
            undefined,
            timestamp,
        );
    }
}
