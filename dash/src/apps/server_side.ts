import { App } from '../apps/app';

import { Decision, Segment, SEGMENT_STATE } from '../common/data';
import { VideoInfo } from '../common/video';
import { logging, exportLogs } from '../common/logger';
import { SetQualityController, onEvent } from '../component/abr';
import { Metrics, StatsTracker } from '../component/stats'; 
import { checking } from '../component/consistency';
import { Interceptor, makeHeader } from '../component/intercept';
import { BackendShim } from '../component/backend';

import { RequestController } from '../controller/request';
import { QualityController } from '../controller/quality';
import { StatsController } from '../controller/stats';

import { ExternalDependency } from '../types';


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
        if (ctx.readyState !== 3) {
            ctx.readyState = 3;
            execute(ctx.onprogress, newEvent('progress', {
                'lengthComputable': true, 
                'loaded': 0, 
                'total': total,
            }));
        }

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


export class ServerSideApp implements App {
    shim: BackendShim;
    tracker: StatsTracker;
    interceptor: Interceptor;
    
    requestController: RequestController;
    qualityController: QualityController;
    statsController: StatsController;

    recordMetrics: boolean;
    max_quality: number;
    max_index: number;

    constructor(
        player: ExternalDependency, 
        recordMetrics: boolean, 
        shim: BackendShim, 
        videoInfo: VideoInfo,
    ) {
        this.shim = shim;
        this.tracker = new StatsTracker(player);
        this.interceptor = new Interceptor(videoInfo);
        
        this.requestController = new RequestController(videoInfo, this.shim, POOL_SIZE);
        this.qualityController = new QualityController();
        this.statsController = new StatsController();
        
        this.recordMetrics = recordMetrics;
        this.max_quality = videoInfo.bitrateArray.length;
        this.max_index = videoInfo.info[videoInfo.bitrateArray[0]].length;
        
        SetQualityController(this.qualityController);
    }

    start() {
        // Request all headers at the beginning
        for (let quality = 1; quality <= this.max_quality; quality++) {
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
            .onPieceSuccess((index: number, body: Body) => {
                onPieceSuccess(index, body);
            })
            .onResourceSend((index: number, url: string, content: string | undefined) => {
                this.interceptor.intercept(index);
            })
            .afterResourceSend((index: number, request: XMLHttpRequest) => {
                this.interceptor.setContext(index, {
                    'xmlRequest': request,
                    'requestObject': this.requestController.getResourceRequest(index),
                });
            })
            .onResourceProgress((index: number, event: Event) => {
               let loaded: number | undefined = (<any>event).loaded; 
               let total: number | undefined = (<any>event).total; 

                // register metrics on progress
                if (loaded !== undefined && total !== undefined) {
                    this.interceptor.progress(index, loaded, total);
                    
                    let segment = new Segment()
                        .withState(SEGMENT_STATE.PROGRESS)
                        .withLoaded(loaded)
                        .withTotal(total)
                        .withIndex(index);
                    let metrics = new Metrics()
                        .withSegment(segment);
                    this.statsController.addMetrics(metrics);
                }
            })
            .onResourceSuccess((index, res) => {
                let quality: number | undefined = this.qualityController.getQuality(index);
                if (quality === undefined) {
                    throw new TypeError(`onResourceSuccess - missing quality:` 
                        + `index ${index}, res ${res}`) 
                }

                // register metrics when a new resource arrives
                let segment = new Segment()
                    .withQuality(<number>quality)
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
                if (index == this.max_index) {
                    // Finish stream if we downloaded everything
                    eos(ctx);
                    return;
                }
                
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
                            let ended: boolean = false;
                            if (request.request !== undefined) {
                                ended = (<any>request.request)._ended;
                            }

                            // if the request did not end
                            if (!ended) {
                                // keep pooling the controller until the request has ended
                                // and when it did restart the controller
                                let startAfterEnded = () => {
                                    let ended: boolean = false;
                                    if (request.request !== undefined) {
                                        ended = (<any>request.request)._ended;
                                    }

                                    if (!ended) {
                                        setTimeout(startAfterEnded, 10);
                                    } else {
                                        controller.start();
                                        logger.log("SchedulingController started.")
                                        if (request.request === undefined) {
                                            throw new TypeError(`missing request for ${request}`);
                                        } else {
                                            onPieceSuccess(
                                                index + 1, (<any>request.request).response.body
                                            );
                                        }
                                    }
                                };
                                
                                logger.log("SchedulingController stopped.")
                                controller.stop();
                                startAfterEnded(); 
                            } else {
                                if (request.request === undefined) {
                                    throw new TypeError(`missing request for ${request}`);
                                } else {
                                    onPieceSuccess(index + 1, (<any>request.request).response.body);
                                }
                            }
                        }
                    }
                });
                
                // send metrics to tracker 
                this.tracker.getMetrics(); 
            })
            .start();
        
        // Listen for stream finishing
        let eos = (_unsued: ExternalDependency) => {
            logger.log('End of stream');
            if (this.recordMetrics) {
                let logs = exportLogs();  
                this.shim
                    .metricsLoggingRequest()
                    .addLogs(logs)
                    .addComplete()
                    .send();
            }
        };
        onEvent("endOfStream", (context: ExternalDependency) => eos(context));
        onEvent("PLAYBACK_ENDED", (context: ExternalDependency) => eos(context));

        onEvent("Detected unintended removal", (context: ExternalDependency) => {
            logger.log('Detected unintdended removal!');
            
            let controller = context.scheduleController;
            controller.start();
        });

        this.tracker.registerCallback((metrics: Metrics) => {
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
