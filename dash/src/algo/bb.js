import { AbrAlgorithm } from '../algo/interface';

import { Decision, Value } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('BB');
const SECOND = 1000;


export class BB extends AbrAlgorithm {
    constructor() {
        super();

        // [TODO] get this from manifest
        this.bitrateArray = [300, 750, 1200, 1850, 2850, 4300]; // in Kbps
        this.lastBufferLevel = new Value(0).withTimestamp(0);
    }

    getDecision(metrics, index, timestamp) {
        logger.log(metrics);
        
        let reservoir = 5 * SECOND;
        let cushion = 10 * SECOND;
        
        this.lastBufferLevel = metrics.bufferLevel.reduce(
            (a, b) => a.timestamp < b.timestamp ? b : a, this.lastBufferLevel);
        let bufferLevel = this.lastBufferLevel.value;
        
        // reference algorithm: 
        // https://github.com/danalex97/pensieve/blob/1120bb173958dc9bc9f2ebff1a8fe688b6f4e93c/dash.js/src/streaming/controllers/AbrController.js#L344

        let bitrateArray = this.bitrateArray;
        let n = bitrateArray.length;

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
