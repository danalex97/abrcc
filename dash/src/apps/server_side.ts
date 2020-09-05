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


/**
 * Simulate an XMLHttp response for the original DASH request to the backend. 
 */
function cacheHit(object, res) {
    let ctx = object.ctx;
    let url = object.url;
    
    const makeWritable = object.makeWritable;
    const execute = object.execute;
    const newEvent = (type, dict) => { 
        return object.newEvent(ctx, type, dict);
    };

   setTimeout(() => {
        // Making response fields writable.
        makeWritable(ctx, 'responseURL', true);
        makeWritable(ctx, 'response', true); 
        makeWritable(ctx, 'readyState', true);
        makeWritable(ctx, 'status', true);
        makeWritable(ctx, 'statusText', true);

        // The request emulating the start of the request. This may 
        // have alreay occured by the dispatch of the onprogress events.
        // 
        // We hence check for XMLHttpRequest's readyState(3 means in progress).
        let total = res.response.byteLength; 
        if (ctx.readyState !== 3) {
            ctx.readyState = 3;
            execute(ctx.onprogress, newEvent('progress', {
                'lengthComputable': true, 
                'loaded': 0, 
                'total': total,
            }));
        }

        // Modify the final response to be the arraybuffer that was requested 
        // via the long-polling request.
        ctx.responseType = "arraybuffer";
        ctx.responseURL = url;
        ctx.response = res.response;
        ctx.readyState = 4;
        ctx.status = 200;
        ctx.statusText = "OK";

        logger.log('Overrided', ctx.responseURL);

        // Call the final onprogress event and the onload event that occurs at the 
        // finish of each XMLHttpRequest. This would normally be called natively by the 
        // XMLHttpRequest browser implementations.
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


/**
 * Back-End based ABR implementations. 
 *
 * Uses an algorithm from the `quic/chromium/src/net/abrcc/abr` folder.
 */
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
        // Request all headers at the beginning.
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
    
        // Callback for each successful piece request. Send the decision to the quality
        // stream for consistency checking and update the QualityController cache.
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

        // Setup long polling mechanism. 
        this.requestController
            .onPieceSuccess((index: number, body: Body) => {
                // When the Decision is received from the backend, start the callback. 
                onPieceSuccess(index, body);
            })
            .onResourceSend((index: number, url: string, content: string | undefined) => {
                // When the resource request was sent, let the interceptor know.
                this.interceptor.intercept(index);
            })
            .afterResourceSend((index: number, request: XMLHttpRequest) => {
                // After the resource was sent(i.e. the send method was called), append 
                // set the interceptor context.
                this.interceptor.setContext(index, {
                    'xmlRequest': request,
                    'requestObject': this.requestController.getResourceRequest(index),
                });
            })
            .onResourceProgress((index: number, event: Event) => {
               let loaded: number | undefined = (<any>event).loaded; 
               let total: number | undefined = (<any>event).total; 

                if (loaded !== undefined && total !== undefined) {
                    // As the download progresses, dispatch the segment progress to the intercetor.
                    // This will maintain correct metrics for DASH as the `onprogress` events are called.
                    this.interceptor.progress(index, loaded, total);
                    
                    // The progress will be registered with the StatsController as well. 
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

                // When the resource(segment) was full downloaded, we firstly register 
                // the metrics.
                let segment = new Segment()
                    .withQuality(<number>quality)
                    .withState(SEGMENT_STATE.DOWNLOADED)
                    .withIndex(index);
                let metrics = new Metrics()
                    .withSegment(segment);
                this.statsController.addMetrics(metrics);

                // Then, we can dispatch the event to the interceptor. This will cause the original
                // XMLHttp request to finish and dispatch the correct DASH callbacks for updating the 
                // buffer and adjusting the video playback.
                this.interceptor.onIntercept(index, (object) => { 
                    cacheHit(object, res);
                });
            })
            .onResourceAbort((index: number, req: XMLHttpRequest) => {
                // On a resource abort, we need to update the quality stream and the metrics being
                // sent to the experimental setup.
                
                // WARN: note this behavior is dependent on the ABR rule specific implementation
                //       from the `src/component/abr.js` file.
                // -- in case that changes, we need to invalidate the index for the streams,
                //    rather than modifying the value to 0
                logger.log('Fixing quality stream at index ', index); 
                qualityStream.replace(index, 0);

                // Add metrics so that the experimental setup knows about the
                // newly uploaded segment.
                let segment = new Segment()
                    .withQuality(0)
                    .withState(SEGMENT_STATE.LOADING)
                    .withIndex(index);
                let metrics = new Metrics()
                    .withSegment(segment);
                logger.log('Sending extra metrics', metrics.serialize(true));
                this.shim
                    .metricsLoggingRequest()
                    .addStats(metrics.serialize(true))
                    .send();
            })
            .start();

        this.interceptor
            .onRequest((ctx, index) => {
                if (index == this.max_index) {
                    // Finish stream if we downloaded everything
                    eos(ctx);
                    return;
                }
                
                // Only when a request is sent, this means that the next 
                // decision of the ABR component will ask for the next 
                // index.
                this.qualityController.advance(index + 1);
                
                // Handle the DASH EventBus that denotes the fragment loading completion.
                // As a frament gets loaded, the ABR rules are prompted for the next segment.
                //
                // In this case, we want to wait for an event that is going to schedule a new piece.
                // This needs to be done if we do not own the decision for the next piece.
                //
                // WARN: Note the details of the implementation below directly interact with DASH 
                // internals specific to version 3.0.0.
                let first = false;
                onEvent("OnFragmentLoadingCompleted", (context) => {
                    if (!first) {
                        first = true;
                        
                        // Stop the player until we receive the decision for piece (index + 1)
                        let controller = context.scheduleController;
                        let request    = this.requestController.getPieceRequest(index + 1); 
                        
                        if (request) {
                            // The request is undefined after we pass all the pieces.
                            logger.log("Scheduling", index + 1);
                            let ended: boolean = false;
                            if (request.request !== undefined) {
                                ended = (<any>request.request)._ended;
                            }

                            // If the request did not end.
                            if (!ended) {
                                // Keep pooling the controller until the request has ended
                                // and when it did restart the controller.
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
                
                // Send metrics to tracker after each new request was sent.
                this.tracker.getMetrics(); 
            })
            .start();
        
        // Listen for stream finishing.
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
                // Send metrics without progress segments to the experimental 
                // setup for centralization purposes.
                this.shim
                    .metricsLoggingRequest()
                    .addStats(allMetrics.serialize(true))
                    .send();
            }

            // Send metrics to the backend.
            this.shim
                .metricsRequest()
                .addStats(allMetrics.serialize())
                .onSuccess((body) => {
                }).onFail(() => {
                }).send();
            
            // Advance the metrics timestamp. This ensures that we will only send fresh information
            // all the time and we will not clutter the pipeline.
            let timestamp = (allMetrics.playerTime.slice(-1)[0] || {'timestamp' : 0}).timestamp;
            allMetrics.segments.forEach((segment) => {
                timestamp = Math.max(segment.timestamp, timestamp);
            });
            this.statsController.advance(timestamp);
        });
        this.tracker.start();
    }
}
