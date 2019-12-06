import { Piece } from '../common/data'; 
import { logging } from '../common/logger';


const logger = logging('PieceCache');


export class PieceCache {
    constructor() {
        this.container = {};
    }

    piece(index) {
        return this.container[index]; 
    }

    insert(piece) {
        if (!(piece instanceof Piece)) {
            throw new TypeError("[PieceCache] wrong type inserted")
        }
        if (this.container[piece.index]) { 
            let currentPiece = this.container[piece.index];
            if (currentPiece.timestamp < piece.timestamp) {
                this.container[piece.index] = piece;
            }
        } else {
            this.container[piece.index] = piece;
        }
        logger.log('piece', this.container[piece.index]);
    }
}
