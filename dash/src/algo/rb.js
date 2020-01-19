import { AbrAlgorithm } from '../algo/interface';
import { ThrpPredictorGetter } from '../algo/getters';

import { Decision, Value } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('RB');


// [TODO] should come from manifest
const bitrateArray = [300, 750, 1200, 1850, 2850, 4300];
const n = bitrateArray.length;


export class RB extends AbrAlgorithm {
    constructor() {
        super();

        this.bandwidth = new ThrpPredictorGetter();
    }
   
    getDecision(metrics, index, timestamp) {
        this.bandwidth.update(metrics, this.ctx);
        let bandwidth = this.bandwidth.value;

        let bitrate = 0;
        let quality = 0;
        for (let i = n - 1; i >= 0; i--) {
            quality = i;
            if (bandwidth >= bitrateArray[i]) {
                break;
            }
        }

        logger.log(`bandwidth ${bandwidth}`, `quality ${quality}`); 
        return new Decision(
            index,
            quality,
            timestamp,
        );
    }
}
