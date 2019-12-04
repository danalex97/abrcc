import { GetServerSideRule } from './component/abr';
import { App } from './app';
import { MediaPlayer } from 'dashjs';
import readingTime from 'reading-time';


function updateAbrSettings(player) {
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
        GetServerSideRule()
    );
}


function init() {
    let url = "https://www.example.org/manifest.mpd";
    let player = MediaPlayer().create();
    let video = document.querySelector('#videoPlayer'); 
    let app = new App(player);
    
    updateAbrSettings(player);
    player.initialize(video, url, true);
    app.start();
}


window.calcRT = ev => { 
    var stats = readingTime(ev.value).text;
    document.getElementById("readingTime").innerText = stats;
};
document.addEventListener("DOMContentLoaded", init);
