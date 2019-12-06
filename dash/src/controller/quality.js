import { logging } from '../common/logger';
import { Decision } from '../common/data';
import { PieceCache } from '../common/cache';  


const logger = logging('QualityController');


export class QualityController {
    constructor() {
        this._cache = new PieceCache();
        this._index = 0;
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
    
    getQuality() {
        let decision = this._cache.piece(this._index);
        if (decision !== undefined) {
            logger.log('new decision', decision);
            return decision.quality;
        } 
        logger.log('default decision');
        return 0;
    }
}
