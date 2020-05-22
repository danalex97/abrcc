import { AbrAlgorithm, MetricGetter } from '../algo/interface';
import { Decision } from '../common/data';
import { logging } from '../common/logger';

import { BufferLevelGetter } from '../algo/getters';
import { LastThrpGetter } from '../algo/getters';
import { RebufferTimeGetter } from '../algo/getters';
import { LastFetchTimeGetter } from '../algo/getters';

import { BackendShim } from '../component/backend';
import { Metrics } from '../component/stats';


const logger = logging('RemoteAbr');


export class RemoteAbr extends AbrAlgorithm {
    shim: BackendShim;
    bandwidth: MetricGetter;
    buffer: MetricGetter;
    rebuffer: MetricGetter;
    fetch_time: MetricGetter;

    constructor(shim: BackendShim) {
        super();

        this.shim = shim;
    
        this.bandwidth = new LastThrpGetter();
        this.buffer = new BufferLevelGetter();
        this.rebuffer = new RebufferTimeGetter();
        this.fetch_time = new LastFetchTimeGetter();
    }
   
    getDecision(metrics: Metrics, index: number, timestamp: number): Decision {
        logger.log(metrics);
        
        this.bandwidth.update(metrics, this.requests);
        this.buffer.update(metrics);
        this.rebuffer.update(metrics);
        this.fetch_time.update(metrics, this.requests);

        // get values
        let bandwidth = this.bandwidth.value;
        let buffer = this.buffer.value;
        let rebuffer = this.rebuffer.value;
        let last_fetch_time = this.fetch_time.value;
        
        logger.log(bandwidth, buffer, rebuffer, last_fetch_time);

        // get decision via sync request
        let decision = undefined;
        this.shim.frontEndDecisionRequest()
            .addIndex(index)
            .addBuffer(buffer)
            .addBandwidth(bandwidth)
            .addRebuffer(rebuffer)
            .addLastFetchTime(last_fetch_time)
            .onSuccessResponse((res) => {
                let response = JSON.parse(res.response);  
                decision = response.decision;
            })
            .send();

        if (decision === undefined) {
            throw new TypeError('FrontEndDecisionRequest failed to fetch decision');
        }
        return new Decision(
            index,
            decision,
            timestamp,
        );
    }
}
