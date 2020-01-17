import { App } from '../apps/app';
import { BB } from '../algo/bb';

import { Decision } from '../common/data';
import { logging, exportLogs } from '../common/logger';
import { Metrics, StatsTracker } from '../component/stats'; 
import { SetQualityController, onEvent } from '../component/abr';
import { Interceptor } from '../component/intercept';

import { QualityController } from '../controller/quality';
import { StatsController } from '../controller/stats';


const logger = logging('App');


export class FrontEndApp extends App {
    constructor(player, recordMetrics, shim) {
        super(player);
    
        this.tracker = new StatsTracker(player);
        this.interceptor = new Interceptor();
        this.shim = shim; 
        
        this.statsController = new StatsController();
        this.qualityController = new QualityController();
        this.algorithm = new BB();

        this.recordMetrics = recordMetrics;

        SetQualityController(this.qualityController);
    }

    start() {
        logger.log("Starting App.")
        this.qualityController
            .onGetQuality((index) => {
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

        onEvent("endOfStream", (context) => {
            logger.log('End of stream');
            if (this.recordMetrics) {
                let logs = exportLogs();  
                this.shim
                    .metricsLoggingRequest()
                    .addLogs(logs)
                    .addComplete()
                    .send();
            }
        });

        this.interceptor
            .onRequest((index) => {
                this.qualityController.advance(index + 1);
                this.tracker.getMetrics(); 
            })
            .start();
        
        this.tracker.registerCallback((metrics) => {
            this.statsController.addMetrics(metrics);
        });

        this.tracker.start();
    }
}
