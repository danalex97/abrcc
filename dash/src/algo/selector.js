import { BB } from '../algo/bb';
import { RB } from '../algo/rb';
import { Festive } from '../algo/festive';
import { Bola } from '../algo/bola';
import { RemoteAbr } from '../algo/remote';


export function GetAlgorithm(name, shim) {
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
    if (name == 'pensieve') {
        return new RemoteAbr(shim);
    }
    if (name == 'robustMpc') {
        return new RemoteAbr(shim);
    }
    return null;
}
