import { BB } from '../algo/bb';
import { RB } from '../algo/rb';


export function GetAlgorithm(name) {
    if (name == 'bb') {
        return new BB();
    }
    if (name == 'rb') {
        return new RB();
    }
    return null;
}
