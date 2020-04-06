import { AbrAlgorithm } from '../algo/interface';
import { ThrpPredictorGetter } from '../algo/getters';

import { Decision, Value } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('RB');


export class RB extends AbrAlgorithm {
    constructor(video) {
        super();

        this.bitrateArray = video.bitrateArray;
        this.n = this.bitrateArray.length;

        this.bandwidth = new ThrpPredictorGetter();
    }
   
    getDecision(metrics, index, timestamp) {
        this.bandwidth.update(metrics, this.ctx);
        let bandwidth = this.bandwidth.value;

        let bitrate = 0;
        let quality = 0;
        for (let i = this.n - 1; i >= 0; i--) {
            quality = i;
            if (bandwidth >= this.bitrateArray[i]) {
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
