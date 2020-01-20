import { logging } from '../common/logger';
import { Decision } from '../common/data';
import { PieceCache } from '../common/cache';  
import { checking } from '../component/consistency';


const logger = logging('QualityController');


export class QualityController {
    constructor() {
        this._cache = new PieceCache();
        this._index = 1;
        
        this._onGetQuality = (index) => {};
    }

    advance(index) {
        if (index < this._index) {
            throw new RangeError(`[QualityController] index ${index} < prev index ${this._index}`);
        }
        this._index = index;
        logger.log('advance', index);
    }

    addPiece(piece) {
        this._cache.insert(piece);
        logger.log('addPiece', piece);
    }
 
    onGetQuality(callback) {
        this._onGetQuality = callback;
        return this;
    }

    getQuality(index, defaultQuality) {
        // If the index is undefined, we use a stateful quality controller,
        // i.e. the index that is calculated via the advance function.
        if (index === undefined) {
            index = this._index;
        }
        
        // handle callbacks
        this._onGetQuality(index);

        // get the decision
        let decision = this._cache.piece(this._index);
        
        if (decision !== undefined) {
            // If the quality we decided upon is 'undefined', this means that 
            // we are using a functionality of Dash, hence we want to use defaultQuality.
            if (decision.quality === undefined) {
                this.addPiece(new Decision(
                    decision.index,
                    defaultQuality,
                    decision.timestamp,
                ));
                return defaultQuality;
            }

            // If this is not the case, we are taking a usual decision.
            return decision.quality;
        } 

        // In principle, our algorithms should never arrive here.
        logger.log("No decision", index, "default decision", 0);
        return 0;
    }
}
