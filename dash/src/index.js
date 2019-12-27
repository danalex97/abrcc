import { ServerSideApp } from './apps/server_side';
import { FrontEndApp } from './apps/front_end';

// config import may fail if config was not generated
import * as config from '../dist/config.json';

import { GetServerSideRule } from './component/abr';
import { MediaPlayer } from 'dashjs';
import readingTime from 'reading-time';


const LARGE_BUFFER_TIME = 100000;
function updateAbrSettings(player) {
    player.updateSettings({
        'streaming': {
            'abr': {
                'useDefaultABRRules': false
            },
            'stableBufferTime': LARGE_BUFFER_TIME, // we use this to request continuously
            'bufferTimeAtTopQuality': LARGE_BUFFER_TIME // we use this to request continously
        },
    });
    console.log(player.getSettings());
    player.addABRCustomRule(
        'qualitySwitchRules', 
        'ServerSideRule', 
        GetServerSideRule()
    );
}


function init() {
    console.log("config", config);
    
    let url = "https://www.example.org/manifest.mpd";
    let player = MediaPlayer().create();
    let video = document.querySelector('#videoPlayer'); 
    let app = new ServerSideApp(player);

    updateAbrSettings(player);
    player.initialize(video, url, true);
    app.start();
}


window.calcRT = ev => { 
    var stats = readingTime(ev.value).text;
    document.getElementById("readingTime").innerText = stats;
};
document.addEventListener("DOMContentLoaded", init);
