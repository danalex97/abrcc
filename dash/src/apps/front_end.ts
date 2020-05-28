import { App } from '../apps/app';
import { GetAlgorithm } from '../algo/selector';
import { AbrAlgorithm } from '../algo/interface';

import { Decision } from '../common/data';
import { VideoInfo } from '../common/video';
import { logging, exportLogs } from '../common/logger';
import { Metrics, StatsTracker } from '../component/stats'; 
import { SetQualityController, onEvent } from '../component/abr';
import { Interceptor } from '../component/intercept';
import { BackendShim } from '../component/backend';

import { QualityController } from '../controller/quality';
import { StatsController } from '../controller/stats';

import { ExternalDependency } from '../types';


const logger = logging('App');


export class FrontEndApp implements App {
    tracker: StatsTracker;
    interceptor: Interceptor;
    shim: BackendShim;
    statsController: StatsController;
    qualityController: QualityController;
    algorithm: AbrAlgorithm;
    recordMetrics: boolean;
    max_index: number;

    constructor(
        player: ExternalDependency, 
        recordMetrics: boolean, 
        shim: BackendShim, 
        name: string, 
        videoInfo: VideoInfo,
    ) {
        this.tracker = new StatsTracker(player);
        this.interceptor = new Interceptor(videoInfo);
        this.shim = shim;
        
        this.statsController = new StatsController();
        this.qualityController = new QualityController();
        this.algorithm = GetAlgorithm(name, shim, videoInfo);

        this.recordMetrics = recordMetrics;
        this.max_index = videoInfo.info[videoInfo.bitrateArray[0]].length;

        SetQualityController(this.qualityController);
    }

    start(): void {
        logger.log("Starting App.")
        this.qualityController
            .onGetQuality((index: number) => {
                this.tracker.getMetrics();
                let controller = this.qualityController;
                
                let metrics = this.statsController.metrics;
                let timestamp = (metrics.playerTime.slice(-1)[0] || {'timestamp' : 0}).timestamp;
                this.statsController.advance(timestamp);
                
                if (this.recordMetrics) {
                    this.shim
                        .metricsLoggingRequest()
                        .addStats(metrics.serialize(true))
                        .send();
                }
                
                let decision = this.algorithm.getDecision(
                    metrics,
                    index,
                    timestamp,
                );
                controller.addPiece(decision);
            });

        let eos = (_unused: ExternalDependency) => {
            logger.log('End of stream');
            if (this.recordMetrics) {
                let logs = exportLogs();  
                this.shim
                    .metricsLoggingRequest()
                    .addLogs(logs)
                    .addComplete()
                    .send();
            }
        };
        onEvent("endOfStream", (context: ExternalDependency) => eos(context));
        onEvent("PLAYBACK_ENDED", (context: ExternalDependency) => eos(context));

        onEvent("Detected unintended removal", (context) => {
            logger.log('Detected unintdended removal!');
           
            let controller = context.scheduleController;
            controller.start();
        });
        
        this.interceptor
            .onRequest((ctx: ExternalDependency, index: number) => {
                if (index == this.max_index) {
                    // Finish stream if we downloaded everything
                    eos(ctx);
                    return;
                }
                
                this.algorithm.newRequest(ctx);

                logger.log('Advance', index + 1);
                this.qualityController.advance(index + 1);
                this.tracker.getMetrics(); 
            })
            .start();
        
        this.tracker.registerCallback((metrics: Metrics) => {
            this.statsController.addMetrics(metrics);
        });

        this.tracker.start();
    }
}
