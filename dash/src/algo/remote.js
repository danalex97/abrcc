import { AbrAlgorithm } from '../algo/interface';
import { Decision } from '../common/data';
import { logging } from '../common/logger';


const logger = logging('RemoteAbr');


export class RemoteAbr extends AbrAlgorithm {
    constructor(shim) {
        super();

        this.shim = shim;
    }
   
    getDecision(metrics, index, timestamp) {
        let decision = undefined;

        // Note this request is synchronous
        this.shim.frontEndDecisionRequest()
            .addIndex(index)
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
