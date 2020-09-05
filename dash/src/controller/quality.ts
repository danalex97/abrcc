import { logging } from '../common/logger';
import { Decision, Piece } from '../common/data';
import { PieceCache } from '../common/cache';  
import { checking } from '../component/consistency';


const logger = logging('QualityController');

/**
 * Controller that received quality Decisions and allows accessing the Decisions taken
 * for a given index. 
 */ 
export class QualityController {
    _index: number;
    _cache: PieceCache;
    _onGetQuality: (index: number) => void;

    constructor() {
        this._cache = new PieceCache();
        this._index = 1;
        
        this._onGetQuality = (index) => {};
    }

    /**
     * Mark that the decision taken for `index` is permament. Will throw a RangeError that marks 
     * inconsistent behavior if the permanent decisions are not announced in order.
     */
    advance(index: number): void {
        if (index < this._index) {
            throw new RangeError(`[QualityController] index ${index} < prev index ${this._index}`);
        }
        this._index = index;
        logger.log('advance', index);
    }

    /**
     * Insert(or update) a new Piece.
     */
    addPiece(piece: Piece): void {
        this._cache.insert(piece);
        logger.log('addPiece', piece);
    }

    /**
     * Allow attaching a *single* callback to be called before the getQuality function returns a 
     * value.
     */
    onGetQuality(callback: (index: number) => void): QualityController {
        this._onGetQuality = callback;
        return this;
    }

    /**
     * Given an index(or otherwise the latest encountered index) return a number representing 
     * the quality of the Piece associated with the segment index present in the cache.
     *
     * In case the decision quality is 'undefined' we return an 'undefined' value as well as the 
     * 'undefault' value marks default functionality in the ABR custom interface of DASH.
     */
    getQuality(index: number | undefined, defaultQuality?: number): number | undefined {
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
            const defaultTimestamp = 0;

            // If the quality we decided upon is 'undefined', this means that 
            // we are using a functionality of Dash, hence we want to use defaultQuality.
            if (decision.quality === undefined) {
                if (decision.timestamp === undefined) {
                    logger.log("WARN: decision with no timestamp: ", decision);
                    decision = new Decision(
                        decision.index,
                        defaultQuality,
                        defaultTimestamp,
                    );
                }
                
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
        logger.log("No decision", index, "defn", 0);
        return 0;
    }
}
