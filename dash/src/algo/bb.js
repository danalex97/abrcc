import { AbrAlgorithm } from '../algo/interface';
import { BufferLevelGetter } from '../algo/getters';

import { Decision, Value } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('BB');
const SECOND = 1000;


// [TODO] should come from manifest
const bitrateArray = [300, 750, 1200, 1850, 2850, 4300];
const n = bitrateArray.length;
const reservoir = 5 * SECOND;
const cushion = 10 * SECOND;


export class BB extends AbrAlgorithm {
    constructor() {
        super();

        this.bufferLevel = new BufferLevelGetter();
    }
   
    getDecision(metrics, index, timestamp) {
        this.bufferLevel.update(metrics);
        let bufferLevel = this.bufferLevel.value;

        let bitrate = 0;
        let quality = 0;
        if (bufferLevel <= reservoir) {
            bitrate = bitrateArray[0];
        } else if (bufferLevel >= reservoir + cushion) {
            bitrate = bitrateArray[n - 1];
        } else {
            bitrate = bitrateArray[0] + (bitrateArray[n - 1] - bitrateArray[0]) * (bufferLevel - reservoir) / cushion;
        }

        for (let i = n - 1; i >= 0; i--) {
            quality = i;
            if (bitrate >= bitrateArray[i]) {
                break;
            }
        }

        logger.log(`bitrate ${bitrate}`, `quality ${quality}`, `buffer level ${bufferLevel}`); 
        return new Decision(
            index,
            quality,
            timestamp,
        );
    }
}
