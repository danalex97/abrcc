import { AbrAlgorithm } from '../algo/interface';
import { BB } from '../algo/bb';
import { RB } from '../algo/rb';
import { Festive } from '../algo/festive';
import { Bola } from '../algo/bola';
import { RemoteAbr } from '../algo/remote';

import { BackendShim } from '../component/backend';
import { VideoInfo } from '../common/video';


export function GetAlgorithm(
    name: string, 
    shim: BackendShim, 
    video: VideoInfo,
): AbrAlgorithm | null {
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
