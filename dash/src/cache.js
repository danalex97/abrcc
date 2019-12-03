class Piece {
    constructor(index, timestamp) {
        this.index = index; 
        this.timestamp = timestamp;
    }
}


class PieceCache {
    constructor() {
        this.container = {}
    }

    get piece(index) {
        return this.container[piece.index]; 
    }

    insert(piece) {
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
