import { MediaPlayer } from 'dashjs';
import readingTime from 'reading-time';

function init() {
    let url = "https://www.example.org/manifest.mpd";
    let player = MediaPlayer().create();
    let video = document.querySelector('#videoPlayer');

    player.initialize(video, url, true);
}

window.calcRT = ev => { 
    var stats = readingTime(ev.value).text;
    document.getElementById("readingTime").innerText = stats;
};
document.addEventListener("DOMContentLoaded", init);
