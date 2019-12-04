import { Value, Segment } from './data'; 


const TICK_INTERVAL_MS = 500;
const MEDIA_TYPE = 'video';


export class Metrics {
    constructor(raw_metrics) {
        this.addSegment(new Segment()
            .withIndex(raw_metrics.scheduling.startTime, raw_metrics.scheduling.duration)
            .withState(raw_metrics.scheduling.state)
            .withTimestamp(raw_metrics.scheduling.t.getTime())
            .withQuality(raw_metrics.scheduling.quality)
        );
        this.addSegment(new Segment() 
            .withUrl(raw_metrics.http_request.url)
            .withTimestamp(raw_metrics.http_request.tresponse.getTime())
        );

        this.dropped_frames = new Value(raw_metrics.dropped.droppedFrames)
            .withTimestamp(raw_metrics.dropped.time.getTime());
        this.player_time = new Value(raw_metrics.info.time * 1000);
        this.buffer_level = new Value(raw_metrics.buffer_level.level)
            .withTimestamp(raw_metrics.buffer_level.t.getTime());
    }

    addSegment(segment) {
        if (this.segments === undefined) {
            this.segments = [];
        }
        if (!isNaN(segment.index) && !isNaN(segment.quality)) {
            this.segments.push(segment);
        }
    }
}


export class StatsTracker {
    constructor(player) {
        this.player = player;
        this.callbacks = [];
    }

    start() {
        setInterval(() => {
            let metrics_wrapper = this.player.getDashMetrics();
            let metrics = this.tick(metrics_wrapper);
            for (let callback of this.callbacks) {
                callback(metrics);
            }
        }, TICK_INTERVAL_MS);
    }

    tick(metrics_wrapper) {
        let getBufferInfo = (info) => metrics_wrapper.getLatestBufferInfoVO(
            MEDIA_TYPE, true, info
        );
        let raw_metrics = {
            'info' : metrics_wrapper.getCurrentDVRInfo(MEDIA_TYPE),
            'dropped' : metrics_wrapper.getCurrentDroppedFrames(),
            'http_request' : metrics_wrapper.getCurrentHttpRequest(MEDIA_TYPE, true),
            'switch' : metrics_wrapper.getCurrentRepresentationSwitch(MEDIA_TYPE, true),
            'scheduling' : metrics_wrapper.getCurrentSchedulingInfo(MEDIA_TYPE),
            'buffer_level' : getBufferInfo('BufferLevel'),
        };

        let metrics = new Metrics(raw_metrics);
        return metrics;
    }

    registerCallback(callback) {
        this.callbacks.push(callback); 
    }
}
