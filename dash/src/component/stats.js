import { timestamp } from '../common/time';
import { Value, Segment, SEGMENT_STATE } from '../common/data';
import { default as stringify } from 'json-stable-stringify';
import { logging } from '../common/logger'; 


const logger = logging('Metrics');
const TICK_INTERVAL_MS = 1000;
const MEDIA_TYPE = 'video';


function pushDefault(context, value) {
    if (context === undefined) {
        context = [];
    }
    context.push(value);
}


export class Metrics {
    constructor(raw_metrics) {
        this.clear();
        if (raw_metrics !== undefined) {
            this.withSegment(new Segment()
                .withStartTime(
                    raw_metrics.scheduling.startTime, 
                    raw_metrics.scheduling.duration)
                .withState(SEGMENT_STATE.LOADING)
                .withTimestamp(timestamp(raw_metrics.scheduling.t))
                .withQuality(raw_metrics.scheduling.quality)
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
  
    clear() {
        this._droppedFrames = [];
        this._bufferLevel = [];
        this._playerTime = [];
        this._segments = [];
        return this;
    }

    serialize() {
        const unique = arr => [...new Set(arr.map(stringify))].map(JSON.parse); 
        const transform = arr => unique(arr.map(x => x.serialize()));
        const cmp = (a, b) => a.timestamp - b.timestamp;
        const prepareSegments = (segments) => {
            const groupBy = (xs, map) => xs.reduce((rv, x) => {
                (rv[map(x)] = rv[map(x)] || []).push(x);
                return rv;
            }, {});
            const statelessFilter = (array, filter) => array.reduce((acc, v) => {
                if (filter(v)) acc.push(v);
                return acc;
            }, []);
            const prepareLoading = (segments) => {
                let out = [];
                let grouped = groupBy(segments, segment => segment.index);
                Object.keys(grouped).forEach(index => {
                    let segment = grouped[index].sort(cmp).slice(-1)[0];
                    out.push(segment);
                });
                return out;
            };
            return transform(
                statelessFilter(segments, s => s.state != SEGMENT_STATE.PROGRESS).concat(
                    prepareLoading(statelessFilter(segments, s => s.state == SEGMENT_STATE.PROGRESS))
                )
            ).sort(cmp);
        };
        return {
            "droppedFrames" : transform(this._droppedFrames).sort(cmp),
            "playerTime" : transform(this._playerTime).sort(cmp),
            "bufferLevel" : transform(this._bufferLevel).sort(cmp),
            "segments" : prepareSegments(this._segments),
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
        if (!isNaN(segment.index)) {
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
        console.log(this.callbacks);
    }

    start() {
        this.getMetrics();
        setInterval(() => {
            this.getMetrics();
        }, TICK_INTERVAL_MS);
    }

    getMetrics(withCallbacks) {
        if (withCallbacks === undefined) {
            withCallbacks = true;
        }
        let metrics_wrapper, metrics;
        try { 
            metrics_wrapper = this.player.getDashMetrics();
            metrics = this.tick(metrics_wrapper);
        } catch(err) {
            metrics = new Metrics();
        }
        if (withCallbacks) {
            for (let callback of this.callbacks) {
                callback(metrics);
            }
        }
    }

    tick(metrics_wrapper) {
        const getBufferInfo = (info) => metrics_wrapper.getLatestBufferInfoVO(
            MEDIA_TYPE, true, info
        );
        const execute = (func, ...args) => {
            try {
                return func(...args);
            } catch (err) {
                return null;
            }
        };

        let raw_metrics = {
            'info' : execute(metrics_wrapper.getCurrentDVRInfo, MEDIA_TYPE),
            'dropped' : execute(metrics_wrapper.getCurrentDroppedFrames),
            'switch' : execute(metrics_wrapper.getCurrentRepresentationSwitch, MEDIA_TYPE, true),
            'scheduling' : execute(metrics_wrapper.getCurrentSchedulingInfo, MEDIA_TYPE),
            'buffer_level' : execute(getBufferInfo, 'BufferLevel'),
        };

        let metrics = new Metrics(raw_metrics);
        return metrics;
    }

    registerCallback(callback) {
        this.callbacks.push(callback); 
    }
}
