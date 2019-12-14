import { timestamp } from '../common/time';
import { Value, Segment } from '../common/data';
import { default as stringify } from 'json-stable-stringify';


const TICK_INTERVAL_MS = 50;
const MEDIA_TYPE = 'video';


function pushDefault(context, value) {
    if (context === undefined) {
        context = [];
    }
    context.push(value);
}


export class Metrics {
    constructor(raw_metrics) {
        this._droppedFrames = [];
        this._bufferLevel = [];
        this._playerTime = [];
        this._segments = [];
        if (raw_metrics !== undefined) {
            this.withSegment(new Segment()
                .withIndex(raw_metrics.scheduling.startTime, raw_metrics.scheduling.duration)
                .withState(raw_metrics.scheduling.state)
                .withTimestamp(timestamp(raw_metrics.scheduling.t))
                .withQuality(raw_metrics.scheduling.quality)
            ).withSegment(new Segment() 
                .withUrl(raw_metrics.http_request.url)
                .withTimestamp(timestamp(raw_metrics.http_request.tresponse))
            ).withDroppedFrames(new Value(raw_metrics.dropped.droppedFrames)
                .withTimestamp(timestamp(raw_metrics.dropped.time))
            ).withPlayerTime(new Value(Math.round(raw_metrics.info.time * 1000))
            ).withBufferLevel(new Value(Math.round(raw_metrics.buffer_level.level))
                .withTimestamp(timestamp(raw_metrics.buffer_level.t))
            );
        }
    }

    _apply(builder, array, filter) {
        if (filter !== undefined) {
            array = array.filter(filter);
        }
        for (let value of array) {
            this[builder](value);    
        }
        return this;
    }

    withMetrics(metrics, filter) {
        return this
            ._apply('withDroppedFrames', metrics.droppedFrames, filter)
            ._apply('withPlayerTime', metrics.playerTime, filter)
            ._apply('withBufferLevel', metrics.bufferLevel, filter)
            ._apply('withSegment', metrics.segments, filter);
    }

    serialize() {
        let unique = arr => [...new Set(arr.map(stringify))].map(JSON.parse); 
        let transform = arr => unique(arr.map(x => x.serialize()));
        let cmp = (a, b) => a.timestamp - b.timestamp;
        return {
            "droppedFrames" : transform(this._droppedFrames).sort(cmp),
            "playerTime" : transform(this._playerTime).sort(cmp),
            "bufferLevel" : transform(this._bufferLevel).sort(cmp),
            "segments" : transform(this._segments).sort(cmp),
        };
    }

    sorted() {
        let cmp = (a, b) => a.timestamp - b.timestamp;
        this._droppedFrames.sort(cmp);
        this._playerTime.sort(cmp);
        this._bufferLevel.sort(cmp);
        this._segments.sort(cmp);
        return this;
    }

    withDroppedFrames(droppedFrames) {
        this._droppedFrames.push(droppedFrames);
        return this;
    }

    withBufferLevel(bufferLevel) {
        this._bufferLevel.push(bufferLevel);
        return this;
    }

    withPlayerTime(playerTime) {
        this._playerTime.push(playerTime);
        return this;
    }

    withSegment(segment) {
        if (!isNaN(segment.index) && !isNaN(segment.quality)) {
            this._segments.push(segment);
        }
        return this;
    }

    get segments() {
        return this._segments;
    }

    get bufferLevel() {
        return this._bufferLevel;
    }

    get playerTime() {
        return this._playerTime;
    }

    get droppedFrames() {
        return this._droppedFrames;
    }
}


export class StatsTracker {
    constructor(player) {
        this.player = player;
        this.callbacks = [];
    }

    start() {
        setInterval(this.getMetrics, TICK_INTERVAL_MS);
    }

    getMetrics() {
        let metrics_wrapper, metrics;
        try { 
            metrics_wrapper = this.player.getDashMetrics();
            metrics = this.tick(metrics_wrapper);
        } catch(err) {
            return; 
        }
        for (let callback of this.callbacks) {
            callback(metrics);
        }
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
