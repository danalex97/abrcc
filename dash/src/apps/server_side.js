import { App } from '../apps/app';

import { Decision, Segment } from '../common/data';
import { logging } from '../common/logger';
import { SetQualityController } from '../component/abr';
import { Metrics, StatsTracker } from '../component/stats'; 
import { BackendShim } from '../component/backend';
import { checking } from '../component/consistency';
import { DataPiece, Interceptor, MAX_QUALITY, makeHeader } from '../component/intercept';

import { RequestController } from '../controller/request';
import { QualityController } from '../controller/quality';
import { StatsController } from '../controller/stats';


const logger = logging('App');
const qualityStream = checking('quality');
const metricsStream = checking('metrics');
const POOL_SIZE = 5;


function cacheHit(object, res) {
    let ctx = object.ctx;
    let url = object.url;
    
    const makeWritable = object.makeWritable;
    const execute = object.execute;
    const newEvent = (type, dict) => { 
        return object.newEvent(ctx, type, dict);
    };

   setTimeout(() => {
        // making response fields writable
        makeWritable(ctx, 'responseURL', true);
        makeWritable(ctx, 'response', true); 
        makeWritable(ctx, 'readyState', true);
        makeWritable(ctx, 'status', true);
        makeWritable(ctx, 'statusText', true);

        // starting
        let total = res.response.byteLength; 
        ctx.readyState = 3;
        execute(ctx.onprogress, newEvent('progress', {
            'lengthComputable': true, 
            'loaded': 0, 
            'total': total,
        }));

        // modify response
        ctx.responseType = "arraybuffer";
        ctx.responseURL = url;
        ctx.response = res.response;
        ctx.readyState = 4;
        ctx.status = 200;
        ctx.statusText = "OK";

        logger.log('Overrided', ctx.responseURL);
        execute(ctx.onprogress, newEvent('progress', {
            'lengthComputable': true, 
            'loaded': total, 
            'total': total,
        }));
        execute(ctx.onload, newEvent('load', {
            'lengthComputable': true, 
            'loaded': total, 
            'total': total,
        }));
        execute(ctx.onloadend);
    }, 0);
}


export class ServerSideApp extends App {
    constructor(player) {
        super(player);

        this.tracker = new StatsTracker(player);
        this.shim = new BackendShim(); 
        this.interceptor = new Interceptor();
        
        this.requestController = new RequestController(this.shim, POOL_SIZE);
        this.qualityController = new QualityController();
        this.statsController = new StatsController();
        
        SetQualityController(this.qualityController);
    }

    start() {
        // Request all headers at the beginning
        for (let quality = 1; quality <= MAX_QUALITY; quality++) {
            let header = makeHeader(quality);
            this.shim
                .headerRequest() 
                .addQuality(quality)
                .onSend((url, content) => {
                    this.interceptor.intercept(header);
                })
                .onSuccessResponse((res) => {
                    this.interceptor.onIntercept(header, (object) => {
                        cacheHit(object, res);
                    });
                }) 
                .send();        
        }

        // Use long polling for the pieces
        this.requestController
            .onPieceSuccess((index, body) => {
                let object = JSON.parse(body);
                let decision = new Decision(
                    object.index,
                    object.quality,
                    object.timestamp
                );
                
                this.qualityController.addPiece(decision);
                qualityStream.push(decision);

                // [TODO] for now we advance the timestamp at each new decision
                this.statsController.advance(decision.timestamp);
            })
            .onResourceSend((index, url, content) => {
                this.interceptor.intercept(index);
            })
            .onResourceSuccess((index, res) => {
                // register metrics when a new resource arrives
                let segment = new Segment()
                    .withQuality(this.qualityController.getQuality(index))
                    .withState('downloaded')
                    .withIndex(index);
                let metrics = new Metrics()
                    .withSegment(segment);
                this.statsController.addMetrics(metrics);

                // add the resource to the cache
                this.interceptor.onIntercept(index, (object) => { 
                    cacheHit(object, res);
                });
            })
            .start();

        this.interceptor
            .onRequest((index) => {
                // only when a request is sent, this means that the next 
                // decision of the abr component will ask for the next 
                // index 
                this.qualityController.advance(index + 1);

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
                    // [TODO] ideally we would like to advance the metrics timestamp here
                }).onFail(() => {
                }).send();
        });
        this.tracker.start();
    }
}
