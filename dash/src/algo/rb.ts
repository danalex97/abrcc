import { AbrAlgorithm, MetricGetter } from '../algo/interface';
import { ThrpPredictorGetter } from '../algo/getters';

import { Decision, Value } from '../common/data';
import { VideoInfo } from '../common/video';
import { logging } from '../common/logger';

import { Metrics } from '../component/stats';


const logger = logging('RB');


export class RB extends AbrAlgorithm {
    bandwidth: MetricGetter;
    bitrateArray: Array<number>; 
    n: number;
 
    constructor(video: VideoInfo) {
        super();

        this.bitrateArray = video.bitrateArray;
        this.n = this.bitrateArray.length;

        this.bandwidth = new ThrpPredictorGetter();
    }
   
    getDecision(metrics: Metrics, index: number, timestamp: number): Decision {
        this.bandwidth.update(metrics, this.requests);
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
