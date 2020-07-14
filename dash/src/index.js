import { logging } from './common/logger';
import { ServerSideApp } from './apps/server_side';
import { FrontEndApp } from './apps/front_end';

// config import may fail if config was not generated
import * as config from '../dist/config.json';
import * as video_config from '../dist/video.json';

import { ArgsParser } from './common/args';
import { VideoInfo } from './common/video';

import { GetServerSideRule } from './component/abr';
import { BackendShim } from './component/backend';
import { MediaPlayer, Debug } from 'dashjs';
import readingTime from 'reading-time';


const logger = logging('index');
const LARGE_BUFFER_TIME = 100000;

    
function updateAbrSettings(player, parser, shim, interceptor) {
    if (!parser.bola && !parser.dynamic) {
        player.updateSettings({
            'streaming': {
                'abr': {
                    'useDefaultABRRules': false,
                    'autoSwitchBitrate' : {
                        'video' : true,
                    },
                },
                'stableBufferTime': LARGE_BUFFER_TIME, // we use this to request continuously
                'bufferTimeAtTopQuality': LARGE_BUFFER_TIME, // we use this to request continously
                'abandonLoadTimeout' : 1000, // make small so abandon request go out early
             },  
            'debug': { 
                'logLevel': Debug.LOG_LEVEL_INFO,
            },
        });
    } else {
        let algo = 'abrBola';
        if (parser.dynamic) {
            algo = 'abrDynamic';
        }
        player.updateSettings({
            'streaming' : {
                'abr' : {
                    'useDefaultABRRules': true,
                    'ABRStrategy': algo,
                    'enableBufferOccupancyABR' : true,
                }
            },
            'debug': { 
                'logLevel': Debug.LOG_LEVEL_INFO,
            },

        });
    }
    logger.log(player.getSettings());
    
    // In the case of Bola, note that the custom rule will be added
    // after the abrThroughput rule is used. This means that if our rule 
    // keeps the same decision we will have no problem with Bola, but still
    // use or components to transmit the metrics.
    let server_side_rule = GetServerSideRule(player, shim, interceptor);
    player.addABRCustomRule(
        'qualitySwitchRules', 
        'ServerSideRule', 
        server_side_rule,
    );
    player.addABRCustomRule(
        'abandonFragmentRules', 
        'AbandonCustomRule', 
        server_side_rule,
    );
}


function startPlayer(app, player, video, url, parser, shim) {
    let interceptor = null;
    if (app.interceptor) {
        interceptor = app.interceptor;
    }
    updateAbrSettings(player, parser, shim, interceptor);
    player.initialize(video, url, true);
    app.start();
    player.play();
}

function init() {
    let parser = new ArgsParser(config.args);
    let video_info = new VideoInfo(video_config);

    let url = `https://${parser.site}:${parser.quicPort}/manifest.mpd`;
    let player = MediaPlayer().create();
    let video = document.querySelector('#videoPlayer'); 
    let app;

    let shim = new BackendShim(parser.site, parser.metricsPort, parser.quicPort);
    if (parser.serverSide) {
        app = new ServerSideApp(
            player, parser.recordMetrics, shim, video_info
        );
    }
    if (!parser.serverSide) {
        app = new FrontEndApp(
            player, parser.recordMetrics, shim, parser.frontEnd, video_info
        );
    }
    if (parser.recordMetrics) {
        shim
            .startLoggingRequest()
            .onSuccess((body) => {
                startPlayer(app, player, video, url, parser, shim);
            })
            .send();
    } else {
        startPlayer(app, player, video, url, parser);
    }
}


window.calcRT = ev => { 
    var stats = readingTime(ev.value).text;
    document.getElementById("readingTime").innerText = stats;
};
document.addEventListener("DOMContentLoaded", init);
