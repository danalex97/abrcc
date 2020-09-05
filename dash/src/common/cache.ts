import { Dict } from '../types';
import { Piece } from '../common/data'; 
import { logging, Logger } from '../common/logger';


const logger: Logger = logging('PieceCache');


/**
 * A dictionary-based cache for Pieces.
 */
export class PieceCache {
    container: Dict<number, Piece>; 
    
    constructor() {
        this.container = {};
    }

    /**
     * Retrieve a piece by the segment index. 
     */
    piece(index: number): Piece {
        return this.container[index]; 
    }

    /**
     * Insert a piece in the cache. If a piece is already present replace it 
     * based on the supplied timestamp.
     */
    insert(piece: Piece): void {
        if (this.container[piece.index]) { 
            let currentPiece = this.container[piece.index];
            if (currentPiece.timestamp < piece.timestamp) {
                this.container[piece.index] = piece;
            }
        } else {
            this.container[piece.index] = piece;
        }
    }
}
