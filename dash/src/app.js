import { Decision } from './common/data';
import { logging } from './common/logger';
import { SetQualityController } from './component/abr';
import { StatsTracker } from './component/stats'; 
import { BackendShim } from './component/backend';
import { checking } from './component/consistency';
import { DataPiece, Interceptor } from './component/intercept';

import { QualityController } from './controller/quality';
import { StatsController } from './controller/stats';


const logger = logging('App');
const qualityStream = checking('quality');
const metricsStream = checking('metrics');


export class App {
    constructor(player) {
        this.tracker = new StatsTracker(player);
        this.shim = new BackendShim(); 
        this.interceptor = new Interceptor();

        this.qualityController = new QualityController();
        this.statsController = new StatsController();
        SetQualityController(this.qualityController);
    }

    start() {
        this.interceptor
            .onRequest((index) => {
                // send new piece request
                this.shim
                    .pieceRequest()
                    .addIndex(index + 1)
                    .onSuccess((body) => {
                        let object = JSON.parse(body);
                        let decision = new Decision(
                            object.index,
                            object.quality,
                            object.timestamp
                        );
                        
                        this.qualityController.addPiece(decision);
                        qualityStream.push(decision);

                        this.qualityController.advance(decision.index);
                        this.statsController.advance(decision.timestamp);
                    }).onFail(() => {
                    }).send();
             
                // send metrics to tracker 
                this.tracker.getMetrics(); 
            })
            .start();
        
        this.tracker.registerCallback((metrics) => {
            // Log metrics
            this.statsController.addMetrics(metrics);
            logger.log("metrics", this.statsController.metrics);

            // Request a new peice from the backend
            let allMetrics = this.statsController.metrics;
            for (let segment of metrics.segments) {
                metricsStream.push(segment);
            }

            this.shim
                .metricsRequest()
                .addStats(allMetrics.serialize())
                .onSuccess((body) => {
                    // [TODO] advance timestamp
                }).onFail(() => {
                }).send();
        });
        this.tracker.start();
    }
}
