import { AbrAlgorithm } from '../algo/interface';
import { Decision } from '../common/data';
import { logging } from '../common/logger';

import { BufferLevelGetter } from '../algo/getters';
import { LastThrpGetter } from '../algo/getters';
import { RebufferTimeGetter } from '../algo/getters';

const logger = logging('RemoteAbr');


export class RemoteAbr extends AbrAlgorithm {
    constructor(shim) {
        super();

        this.shim = shim;
    
        this.bandwidth = new LastThrpGetter();
        this.buffer = new BufferLevelGetter();
        this.rebuffer = new RebufferTimeGetter();
    }
   
    getDecision(metrics, index, timestamp) {
        this.bandwidth.update(metrics, this.ctx);
        this.buffer.update(metrics);
        this.rebuffer.update(metrics);

        // get values
        let bandwidth = this.bandwidth.value;
        let buffer = this.buffer.value;
        let rebuffer = this.rebuffer.value;

        // get decision via sync request
        let decision = undefined;
        this.shim.frontEndDecisionRequest()
            .addIndex(index)
            .addBuffer(buffer)
            .addBandwidth(bandwidth)
            .addRebuffer(rebuffer)
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
