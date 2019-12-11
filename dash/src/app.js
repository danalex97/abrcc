import { Decision } from './common/data';
import { logging } from './common/logger';
import { SetQualityController } from './component/abr';
import { StatsTracker } from './component/stats'; 
import { BackendShim } from './component/backend';
import { checking } from './component/consistency';
import { QualityController } from './controller/quality';
import { StatsController } from './controller/stats';
import { RequestController } from './controller/request';

const logger = logging('App');
const qualityStream = checking('quality');
const metricsStream = checking('metrics');
const POOL_SIZE = 10;


export class App {
    constructor(player) {
        this.tracker = new StatsTracker(player);
        this.shim = new BackendShim(); 
        
        this.qualityController = new QualityController();
        this.statsController = new StatsController();
        this.requestController = new RequestController(POOL_SIZE, this.shim);

        SetQualityController(this.qualityController);
    }

    start() {
        this.requestController
            .onSuccess((index, body) => {
                let rawData = body;
                
                let sep = '$$$$';
                let pos = rawData.indexOf(sep);

                let url = rawData.substring(0, pos);
                let data = rawData.substring(pos + sep.length);
           
                logger.log("New piece", url, data.length); 
                
                // [TODO] do stuff with the data
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
                    // this.qualityController.addPiece(decision);
                    // qualityStream.push(decision);

                    // this.qualityController.advance(decision.index);
                    // this.statsController.advance(decision.timestamp);
                }).onFail(() => {
                }).send();
        });
        this.tracker.start();
    }
}
