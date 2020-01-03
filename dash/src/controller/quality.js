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

    getQuality(index) {
        if (index === undefined) {
            index = this._index;
        }
        this._onGetQuality(index);
        let decision = this._cache.piece(this._index);
        if (decision !== undefined) {
            return decision.quality;
        } 
        logger.log("No decision", index, "default decision", 0);
        return 0;
    }
}
