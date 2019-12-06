import { Decision } from './common/data';
import { logging } from './common/logger';
import { SetQualityController } from './component/abr';
import { StatsTracker } from './component/stats'; 
import { BackendShim } from './component/backend';
import { checking } from './component/consistency';
import { QualityController } from './controller/quality';
import { StatsController } from './controller/stats';


const logger = logging('App');
const qualityStream = checking('quality');
const metricsStream = checking('metrics');


export class App {
    constructor(player) {
        this.qualityController = new QualityController();
        this.statsController = new StatsController();

        this.tracker = new StatsTracker(player);
        this.shim = new BackendShim(); 
        
        SetQualityController(this.qualityController);
    }

    start() {
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
                .request()
                .addStats(allMetrics.serialize())
                .addPieceRequest()
                .onSuccess((body) => {
                    let decision = new Decision(
                        body.index,
                        body.quality,
                        body.timestamp,
                    );
                    this.qualityController.addPiece(decision);
                    qualityStream.push(decision);

                    this.qualityController.advance(decision.index);
                    this.statsController.advance(decision.timestamp);
                }).onFail(() => {
                    logger.log("request failed")
                }).send();
        });
        this.tracker.start();
    }
}
