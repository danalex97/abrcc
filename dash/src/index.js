import { GetServerSideRule } from './component/abr';
import { StatsTracker } from './component/stats'; 
import { BackendShim } from './component/backend';
import { QualityController } from './controller/quality';
import { StatsController } from './controller/stats';
import { MediaPlayer } from 'dashjs';
import readingTime from 'reading-time';

function init() {
    let url = "https://www.example.org/manifest.mpd";
    let player = MediaPlayer().create();
    let video = document.querySelector('#videoPlayer');
    
    let qualityController = new QualityController();
    let statsController = new StatsController();

    player.updateSettings({
        'streaming': {
            'abr': {
                'useDefaultABRRules': false
            }
        }
    });
    player.addABRCustomRule(
        'qualitySwitchRules', 
        'ServerSideRule', 
        GetServerSideRule(qualityController)
    );
    player.initialize(video, url, true);

    let shim = new BackendShim();
    shim.request().addPieceRequest().send().then(console.log);

    let tracker = new StatsTracker(player);
    tracker.registerCallback((metrics) => {
        statsController.addMetrics(metrics);
        console.log(statsController.metrics);
    });
    tracker.start();
}

window.calcRT = ev => { 
    var stats = readingTime(ev.value).text;
    document.getElementById("readingTime").innerText = stats;
};
document.addEventListener("DOMContentLoaded", init);
