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
        this.shim.request().addPieceRequest().send().then(console.log);
        this.tracker.registerCallback((metrics) => {
            this.statsController.addMetrics(metrics);
            console.log(this.statsController.metrics);
        });
        this.tracker.start();
    }
}
