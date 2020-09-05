import { AbrAlgorithm, MetricGetter } from '../algo/interface';
import { ThrpPredictorGetter } from '../algo/getters';

import { Decision, Value } from '../common/data';
import { VideoInfo } from '../common/video';
import { logging } from '../common/logger';

import { Dict } from '../types';

import { Metrics } from '../component/stats';


const logger = logging('Festive');
const diminuation_factor = 0.85;
const alpha = 12;
const horizon = 5;
const switchUpThreshold = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];


/**
 * Festive(https://dl.acm.org/doi/10.1145/2413176.2413189) is a rate-based approach that uses a 
 * windowed harmonic mean for bandwidth estimation. The code has mostly been ported from the Pensive
 * repository: https://github.com/hongzimao/pensieve.
 */
export class Festive extends AbrAlgorithm {
    bitrateArray: Array<number>; 
    n: number;
    
    bandwidth: MetricGetter;
    
    qualityLog: Dict<number, number>;
    prevQuality: number;
    lastIndex: number;
    switchUpCount: number;

    constructor(video: VideoInfo) {
        super();

        this.bitrateArray = video.bitrateArray;
        this.n = this.bitrateArray.length;

        this.bandwidth = new ThrpPredictorGetter();
        
        this.qualityLog = { 0 : 0 };
        this.prevQuality = 0;
        this.lastIndex = 0;
        this.switchUpCount = 0;
    }

    /**
     * Selects a `quality` for a `bitrate`. Select the first quality for which the associated 
     * bitrateArray value stays below the `bitrate`.
     */
    selectQuality(bitrate: number): number {
        let quality = this.n;
        for (let i = this.n - 1; i >= 0; i--) {
            quality = i;
            if (bitrate >= this.bitrateArray[i]) {
                break;
            }
        }
        return quality;
    }

    /**
     * Given the current quality `b` and a reference quality `b_ref` and a bandwidth prediction 
     * `w` compute the efficiency score as presented in the paper.
     */
    getEfficiencyScore(b: number, b_ref: number, w: number): number {
        return Math.abs(this.bitrateArray[b] 
            / Math.min(w, this.bitrateArray[b_ref]) - 1);
    }


    /**
     * Given the current candate quality `b`, a reference quality `b_ref`, a candidate quality `b_cur`
     * compute the stability score as presented in the paper.
     */
    getStabilityScore(b: number, b_ref: number, b_cur: number): number {
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

    getCombinedScore(b: number, b_ref: number, b_cur: number, w: number): number {
        let stabilityScore  = this.getStabilityScore(b, b_ref, b_cur);
        let efficiencyScore = this.getEfficiencyScore(b, b_ref, w);
        return stabilityScore + alpha * efficiencyScore;
    }

    /**
     * The decision is taken as follows:
     *   - compute a target quality: b_target based on the future bandwidth prediction
     *   - compute the new reference target quality: b_ref which is limited by number of upward quality
     *     changes
     *   - keep or modify the quality based on the computed combined scores for the qualities 
     */
    getDecision(metrics: Metrics, index: number, timestamp: number): Decision {
        this.bandwidth.update(metrics, this.requests);
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
