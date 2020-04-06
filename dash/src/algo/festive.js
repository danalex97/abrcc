import { AbrAlgorithm } from '../algo/interface';
import { ThrpPredictorGetter } from '../algo/getters';

import { Decision, Value } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('Festive');
const diminuation_factor = 0.85;
const alpha = 12;
const horizon = 5;
const switchUpThreshold = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];


export class Festive extends AbrAlgorithm {
    constructor(video) {
        super();

        this.bitrateArray = video.bitrateArray;
        this.n = this.bitrateArray.length;

        this.bandwidth = new ThrpPredictorGetter();
        
        this.qualityLog = { 0 : 0 };
        this.prevQuality = 0;
        this.lastIndex = 0;
        this.switchUpCount = 0;
    }

    selectQuality(bitrate) {
        let quality = this.n;
        for (let i = this.n - 1; i >= 0; i--) {
            quality = i;
            if (bitrate >= this.bitrateArray[i]) {
                break;
            }
        }
        return quality;
    }

    getEfficiencyScore(b, b_ref, w) {
        return Math.abs(this.bitrateArray[b] 
            / Math.min(w, this.bitrateArray[b_ref]) - 1);
    }

    getStabilityScore(b, b_ref, b_cur) {
        var score = 0,
            changes = 0;
        if (this.lastIndex >= 1) {
            let start = Math.max(0, this.lastIndex + 1 - horizon);
            let end = this.lastIndex - 1;
            for (let i = start; i <= end; i++) {
                if (this.qualityLog[i] != this.qualityLog[i + 1]) {
                    changes++;
                }
            }
        }
        if (b != b_cur) {
            changes += 1;
        }
        score = Math.pow(2, changes);
        return score;
    }

    getCombinedScore(b, b_ref, b_cur, w) {
        let stabilityScore  = this.getStabilityScore(b, b_ref, b_cur);
        let efficiencyScore = this.getEfficiencyScore(b, b_ref, w);
        return stabilityScore + alpha * efficiencyScore;
    }

    getDecision(metrics, index, timestamp) {
        this.bandwidth.update(metrics, this.ctx);
        let bwPrediction = this.bandwidth.value;

        // compute b_target
        let b_target = this.selectQuality(diminuation_factor * bwPrediction);
        
        // compute b_ref
        let b_cur = this.prevQuality;
        let b_ref = 0;
        if (b_target > b_cur) {
            this.switchUpCount = this.switchUpCount + 1;
            if (this.switchUpCount > switchUpThreshold[b_cur]) {
                b_ref = b_cur + 1;
            } else {
                b_ref = b_cur;
            }
        } else if (b_target < b_cur) {
            b_ref = b_cur - 1;
            this.switchUpCount = 0;
        } else {
            b_ref = b_cur;
            this.switchUpCount = 0;
        }
        
        // delayed update
        let quality = 0;
        if (b_ref != b_cur) {
            // compute scores
            let score_cur = this.getCombinedScore(b_cur, b_ref, b_cur, bwPrediction);
            let score_ref = this.getCombinedScore(b_ref, b_ref, b_cur, bwPrediction);
            logger.log(`score cur ${b_cur} -> ${score_cur}`, `score ref ${b_ref} -> ${score_ref}`);  

            if (score_cur <= score_ref) {
                quality = b_cur;
            } else {
                quality = b_ref;
                if (quality > b_cur) {
                    this.switchUpCount = 0;
                }
            }
        } else {
            quality = b_cur;
        }

        // log relevant info for festive
        logger.log(`quality ${quality}`, `b_target ${b_target}`);

        // update quality log
        this.qualityLog[index] = this.bitrateArray[quality];
        this.prevQuality = quality;
        this.lastIndex = index;

        return new Decision(
            index,
            quality,
            timestamp,
        );
    }
}
