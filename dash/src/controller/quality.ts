import { logging } from '../common/logger';
import { Decision, Piece } from '../common/data';
import { PieceCache } from '../common/cache';  
import { checking } from '../component/consistency';


const logger = logging('QualityController');


export class QualityController {
    _index: number;
    _cache: PieceCache;
    _onGetQuality: (index: number) => void;

    constructor() {
        this._cache = new PieceCache();
        this._index = 1;
        
        this._onGetQuality = (index) => {};
    }

    advance(index: number): void {
        if (index < this._index) {
            throw new RangeError(`[QualityController] index ${index} < prev index ${this._index}`);
        }
        this._index = index;
        logger.log('advance', index);
    }

    addPiece(piece: Piece): void {
        this._cache.insert(piece);
        logger.log('addPiece', piece);
    }
 
    onGetQuality(callback: (index: number) => void): QualityController {
        this._onGetQuality = callback;
        return this;
    }
 
    getQuality(index: number | undefined, defaultQuality: number | undefined): number | undefined {
        // If the index is undefined, we use a stateful quality controller,
        // i.e. the index that is calculated via the advance function.
        if (index === undefined) {
            index = this._index;
        } else if (index > this._index) {
            // !THIS SHOULD NOT HAPPEN
            logger.log("WARN: ", index, "in front of ", this._index);
        }
        
        // handle callbacks
        this._onGetQuality(index);

        // get the decision for index(note: not this._index)
        let decision = this._cache.piece(index);
        
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
