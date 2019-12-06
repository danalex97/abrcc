import { Decision } from '../common/data';
import { PieceCache } from '../common/cache';  


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
    }

    addPiece(piece) {
        this._cache.insert(piece);
    }
    
    getQuality() {
        let decision = this._cache[this._index];
        if (decision !== undefined) {
            console.log('[QualityController] new decision:');
            console.log(decision);
            return decision.quality;
        } 
        console.log('[QualityController] default decision');
        return 0;
    }
}
