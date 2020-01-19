import { App } from '../apps/app';

import { Decision, Segment, SEGMENT_STATE } from '../common/data';
import { logging, exportLogs } from '../common/logger';
import { SetQualityController, onEvent } from '../component/abr';
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
    constructor(player, recordMetrics, shim) {
        super(player);

        this.shim = shim;
        this.tracker = new StatsTracker(player);
        this.interceptor = new Interceptor();
        
        this.requestController = new RequestController(this.shim, POOL_SIZE);
        this.qualityController = new QualityController();
        this.statsController = new StatsController();
        
        this.recordMetrics = recordMetrics;
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

        let onPieceSuccess = (index, body) => {
            let object = JSON.parse(body);
            let decision = new Decision(
                object.index,
                object.quality,
                object.timestamp
            );
            
            this.qualityController.addPiece(decision);
            qualityStream.push(decision);
        };

        // Use long polling for the pieces
        this.requestController
            .onPieceSuccess((index, body) => {
                onPieceSuccess(index, body);
            })
            .onResourceSend((index, url, content) => {
                this.interceptor.intercept(index);
            })
            .onResourceProgress((index, event) => {
                // register metrics on progress
                if (event.loaded !== undefined && event.total !== undefined) {
                    let segment = new Segment()
                        .withState(SEGMENT_STATE.PROGRESS)
                        .withLoaded(event.loaded)
                        .withTotal(event.total)
                        .withIndex(index);
                    let metrics = new Metrics()
                        .withSegment(segment);
                    this.statsController.addMetrics(metrics);
                }
            })
            .onResourceSuccess((index, res) => {
                // register metrics when a new resource arrives
                let segment = new Segment()
                    .withQuality(this.qualityController.getQuality(index))
                    .withState(SEGMENT_STATE.DOWNLOADED)
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
            .onRequest((ctx, index) => {
                // only when a request is sent, this means that the next 
                // decision of the abr component will ask for the next 
                // index 
                this.qualityController.advance(index + 1);
                
                // we wait for an event that is going to schedule a new 
                // piece
                let first = false;
                onEvent("OnFragmentLoadingCompleted", (context) => {
                    if (!first) {
                        first = true;
                        
                        // Stop the player until we receive the decision for piece
                        // index + 1
                        let controller = context.scheduleController;
                        let request    = this.requestController.getPieceRequest(index + 1); 
                        
                        if (request) {
                            // the request is undefined after we pass all the pieces 
                            logger.log("Scheduling", index + 1);
                            if (!request.request._ended) {
                                let startAfterEnded = () => {
                                    if (!request.request._ended) {
                                        setTimeout(startAfterEnded, 10);
                                    } else {
                                        controller.start();
                                        logger.log("SchedulingController started.")
                                        onPieceSuccess(index + 1, request.request.response.body);
                                    }
                                };
                                
                                logger.log("SchedulingController stopped.")
                                controller.stop();
                                startAfterEnded(); 
                            } else {
                                onPieceSuccess(index + 1, request.request.response.body);
                            }
                        }
                    }
                });
                
                // send metrics to tracker 
                this.tracker.getMetrics(); 
            })
            .start();
        
        // Listen for stream finishing
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

        this.tracker.registerCallback((metrics) => {
            // Log metrics
            this.statsController.addMetrics(metrics);

            // Push segments to the metrics stream for consistency checks
            let allMetrics = this.statsController.metrics;
            for (let segment of metrics.segments) {
                if (segment.state != SEGMENT_STATE.PROGRESS) {
                    metricsStream.push(segment);
                }
            }

            if (this.recordMetrics) {
                // Send metrics without progress segments
                this.shim
                    .metricsLoggingRequest()
                    .addStats(allMetrics.serialize(true))
                    .send();
            }

            // Send metrics to backend
            this.shim
                .metricsRequest()
                .addStats(allMetrics.serialize())
                .onSuccess((body) => {
                }).onFail(() => {
                }).send();
            
            // Advance timestamp
            let timestamp = (allMetrics.playerTime.slice(-1)[0] || {'timestamp' : 0}).timestamp;
            allMetrics.segments.forEach((segment) => {
                timestamp = Math.max(segment.timestamp, timestamp);
            });
            this.statsController.advance(timestamp);
        });
        this.tracker.start();
    }
}
