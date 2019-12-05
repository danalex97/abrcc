import { SetQualityController } from './component/abr';
import { StatsTracker } from './component/stats'; 
import { BackendShim } from './component/backend';
import { QualityController } from './controller/quality';
import { StatsController } from './controller/stats';


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
            console.log(this.statsController.metrics);
             
            // Request a new peice from the backend
            let allMetrics = this.statsController.metrics;
            this.shim
                .request()
                .addStats(allMetrics.serialize())
                .addPieceRequest()
                .onSuccess((body) => {
                    // [TODO] should use the body to talk to the 
                    // quality and stats controllers 
                }).onFail(() => {
                    console.log("[App] Request failed")
                }).send();
        });
        this.tracker.start();
    }
}
