import { BB } from '../algo/bb';
import { RB } from '../algo/rb';
import { Festive } from '../algo/festive';
import { Bola } from '../algo/bola';


export function GetAlgorithm(name) {
    if (name == 'bb') {
        return new BB();
    }
    if (name == 'rb') {
        return new RB();
    }
    if (name == 'festive') {
        return new Festive();
    }
    if (name == 'bola') {
        return new Bola();
    }
    return null;
}
