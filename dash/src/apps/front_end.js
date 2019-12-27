import { App } from '../apps/app';

import { Decision } from '../common/data';
import { logging } from '../common/logger';
import { Metrics, StatsTracker } from '../component/stats'; 
import { SetQualityController } from '../component/abr';
import { Interceptor } from '../component/intercept';

import { QualityController } from '../controller/quality';
import { StatsController } from '../controller/stats';


const logger = logging('App');


export class FrontEndApp extends App {
    constructor(player) {
        super(player);
    
        this.tracker = new StatsTracker(player);
        this.interceptor = new Interceptor();
        
        this.statsController = new StatsController();
        this.qualityController = new QualityController();
    
        SetQualityController(this.qualityController);
    }

    start() {
        logger.log("Starting App.")

        this.qualityController
            .onGetQuality((index) => {
                let controller = this.qualityController;
                
                let metrics = this.statsController.metrics;
                let timestamp = (metrics.playerTime.slice(-1)[0] || {'timestamp' : 0}).timestamp;
                this.statsController.advance(timestamp);

                logger.log("new metrics", timestamp, metrics);
                
                // [TODO] put an actual algorithm here
                let quality = 0;
                let decision = new Decision(
                    index,
                    quality,
                    timestamp
                );
                controller.addPiece(decision);
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
