import { BB } from '../algo/bb';
import { RB } from '../algo/rb';
import { Festive } from '../algo/festive';
import { Bola } from '../algo/bola';
import { RemoteAbr } from '../algo/remote';


export function GetAlgorithm(name, shim, video) {
    if (name == 'bb') {
        return new BB(video);
    }
    if (name == 'rb') {
        return new RB(video);
    }
    if (name == 'festive') {
        return new Festive(video);
    }
    if (name == 'bola') {
        return new Bola(video);
    }
    if (name == 'pensieve') {
        return new RemoteAbr(shim);
    }
    if (name == 'robustMpc') {
        return new RemoteAbr(shim);
    }
    return null;
}
