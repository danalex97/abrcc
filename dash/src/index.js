import { GetServerSideRule } from './abr';
import { QualityController } from './controller';
import { StatsTracker } from './stats'; 
import { MediaPlayer } from 'dashjs';
import readingTime from 'reading-time';

function init() {
    let url = "https://www.example.org/manifest.mpd";
    let player = MediaPlayer().create();
    let video = document.querySelector('#videoPlayer');
    let controller = new QualityController();

    player.updateSettings({
        'streaming': {
            'abr': {
                'useDefaultABRRules': false
            }
        }
    });
    console.log(controller);
    player.addABRCustomRule(
        'qualitySwitchRules', 
        'ServerSideRule', 
        GetServerSideRule(controller)
    );
    player.initialize(video, url, true);

    let tracker = new StatsTracker(player);
    tracker.registerCallback((metrics) => {
        console.log(metrics);
    });
    tracker.start();
}

window.calcRT = ev => { 
    var stats = readingTime(ev.value).text;
    document.getElementById("readingTime").innerText = stats;
};
document.addEventListener("DOMContentLoaded", init);
