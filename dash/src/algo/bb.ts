import { AbrAlgorithm, MetricGetter } from '../algo/interface';
import { BufferLevelGetter } from '../algo/getters';

import { Decision, Value } from '../common/data';
import { VideoInfo } from '../common/video';
import { logging } from '../common/logger';

import { Metrics } from '../component/stats';


const logger = logging('BB');
const SECOND = 1000;


const reservoir = 5 * SECOND;
const cushion = 10 * SECOND;


/**
 * Buffer-based ABR algorithm
 *
 * If the buffer is below the `reservoir`, we use the smallest available quality level.
 * If the buffer is above `cushion + reservoir`, we use the highest available quality level.
 *
 * If the buffer is in the `cushion` interval, we use the first bitrate proportial with the 
 * occupied buffer out of the cushion space, i.e. `(bufferLevel - reservoir) / cushion`.
 */
export class BB extends AbrAlgorithm {
    bufferLevel: MetricGetter;
    bitrateArray: Array<number>; 
    n: number;
    
    constructor(video: VideoInfo) {
        super();

        this.bitrateArray = video.bitrateArray;
        this.n = this.bitrateArray.length;
        this.bufferLevel = new BufferLevelGetter();
    }
   
    getDecision(metrics: Metrics, index: number, timestamp: number): Decision {
        this.bufferLevel.update(metrics);
        let bufferLevel = this.bufferLevel.value;

        let bitrate = 0;
        let quality = 0;
        if (bufferLevel <= reservoir) {
            bitrate = this.bitrateArray[0];
        } else if (bufferLevel >= reservoir + cushion) {
            bitrate = this.bitrateArray[this.n - 1];
        } else {
            bitrate = this.bitrateArray[0] + 
               (this.bitrateArray[this.n - 1] - this.bitrateArray[0]) * 
               (bufferLevel - reservoir) / cushion;
        }

        for (let i = this.n - 1; i >= 0; i--) {
            quality = i;
            if (bitrate >= this.bitrateArray[i]) {
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
