import { AbrAlgorithm } from '../algo/interface';
import { Decision } from '../common/data';
import { logging } from '../common/logger';

import { BufferLevelGetter } from '../algo/getters';
import { LastThrpGetter } from '../algo/getters';
import { RebufferTimeGetter } from '../algo/getters';
import { LastFetchTimeGetter } from '../algo/getters';


const logger = logging('RemoteAbr');


export class RemoteAbr extends AbrAlgorithm {
    constructor(shim) {
        super();

        this.shim = shim;
    
        this.bandwidth = new LastThrpGetter();
        this.buffer = new BufferLevelGetter();
        this.rebuffer = new RebufferTimeGetter();
        this.fetch_time = new LastFetchTimeGetter();
    }
   
    getDecision(metrics, index, timestamp) {
        this.bandwidth.update(metrics, this.ctx);
        this.buffer.update(metrics);
        this.rebuffer.update(metrics);
        this.fetch_time.update(metrics, this.ctx);

        // get values
        let bandwidth = this.bandwidth.value;
        let buffer = this.buffer.value;
        let rebuffer = this.rebuffer.value;
        let last_fetch_time = this.fetch_time.value;

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
        
        return new Decision(
            index,
            decision,
            timestamp,
        );
    }
}
