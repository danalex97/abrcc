import { Dict } from '../types';
import { Piece } from '../common/data'; 
import { logging, Logger } from '../common/logger';


const logger: Logger = logging('PieceCache');


export class PieceCache {
    container: Dict<number, Piece>; 
    
    constructor() {
        this.container = {};
    }

    piece(index): Piece {
        return this.container[index]; 
    }

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
