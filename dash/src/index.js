import { logging } from './common/logger';
import { ServerSideApp } from './apps/server_side';
import { FrontEndApp } from './apps/front_end';

// config import may fail if config was not generated
import * as config from '../dist/config.json';

import { ArgsParser } from './common/args';
import { GetServerSideRule } from './component/abr';
import { MediaPlayer, Debug } from 'dashjs';
import readingTime from 'reading-time';


const logger = logging('index');
const LARGE_BUFFER_TIME = 100000;

    
function updateAbrSettings(player) {
    player.updateSettings({
        'streaming': {
            'abr': {
                'useDefaultABRRules': false
            },
            'stableBufferTime': LARGE_BUFFER_TIME, // we use this to request continuously
            'bufferTimeAtTopQuality': LARGE_BUFFER_TIME, // we use this to request continously
        },  
        'debug': { 
            'logLevel': Debug.LOG_LEVEL_INFO,
        },
    });
    console.log(player.getSettings());
    player.addABRCustomRule(
        'qualitySwitchRules', 
        'ServerSideRule', 
        GetServerSideRule(player)
    );
}


function init() {
    let parser = new ArgsParser(config.args);

    let url = "https://www.example.org/manifest.mpd";
    let player = MediaPlayer().create();
    let video = document.querySelector('#videoPlayer'); 
    let app;

    if (parser.serverSide) {
        app = new ServerSideApp(player, parser.recordMetrics);
    }
    if (parser.frontEnd) {
        app = new FrontEndApp(player, parser.recordMetrics);
    }

    updateAbrSettings(player);
    player.initialize(video, url, true);
    app.start();
}


window.calcRT = ev => { 
    var stats = readingTime(ev.value).text;
    document.getElementById("readingTime").innerText = stats;
};
document.addEventListener("DOMContentLoaded", init);
