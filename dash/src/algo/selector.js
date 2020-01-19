import { BB } from '../algo/bb';
import { RB } from '../algo/rb';
import { Festive } from '../algo/festive';


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
    return null;
}
