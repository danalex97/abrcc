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

    sendPieceRequest(index) {
        this.shim
            .pieceRequest()
            .addIndex(index)
            .onSuccess((body) => {
                let object = JSON.parse(body);
                let decision = new Decision(
                    object.index,
                    object.quality,
                    object.timestamp
                );
                
                this.qualityController.addPiece(decision);
                qualityStream.push(decision);

                // [TODO] check this is legit
                // this.qualityController.advance(decision.index);
                this.statsController.advance(decision.timestamp);
            }).onFail(() => {
            }).send();
        
        this.shim
            .resourceRequest()
            .addIndex(index)
            .onSend((url, content) => {
                // we intercept future requests to the backend
                this.interceptor.intercept(index);
            })
            .onSuccessResponse((res) => {
                this.interceptor.onIntercept(index, (object) => { 
                    let ctx = object.ctx;
                    let makeWritable = object.makeWritable;
                    let url = object.url;

                    // make writable
                    makeWritable(ctx, 'responseURL', true);
                    makeWritable(ctx, 'response', true); 
                    makeWritable(ctx, 'readyState', true);
                    makeWritable(ctx, 'status', true);
                    makeWritable(ctx, 'statusText', true);
                   
                    // starting
                    ctx.readyState = 3;
                    if (ctx.onreadystatechange) {
                        ctx.onreadystatechange();
                    }

                    // modify response
                    ctx.responseType = "arraybuffer";
                    ctx.responseURL = url;
                    ctx.response = res.response;
                    ctx.readyState = 4;
                    ctx.status = 200;
                    ctx.statusText = "OK";

                    // make unwritable
                    makeWritable(ctx, 'responseURL', false);
                    makeWritable(ctx, 'response', false); 
                    makeWritable(ctx, 'readyState', false);
                    makeWritable(ctx, 'status', false);
                    makeWritable(ctx, 'statusText', false);
                    logger.log('Overrided', ctx.responseURL);
                   
                    // do callbacks
                    if (ctx.onreadystatechange) {
                        ctx.onreadystatechange();
                    }
                    if (ctx.onload) {
                        ctx.onload();
                    }
                    if (ctx.onloadend) {
                        ctx.onloadend(); 
                    }
                });
            }).onFail(() => {
            }).send();
    }

    start() {
        this.sendPieceRequest(1);
    
        this.interceptor
            .onRequest((index) => {
                // send new piece request
                this.sendPieceRequest(index + 1);

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
