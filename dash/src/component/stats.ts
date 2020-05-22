import { Json, ExternalDependency } from '../types';
import { timestamp } from '../common/time';
import { Value, Segment, SEGMENT_STATE } from '../common/data';
import { default as stringify } from 'json-stable-stringify';
import { logging, Logger } from '../common/logger'; 


const logger: Logger = logging('Metrics');
const TICK_INTERVAL_MS: number = 100;
const MEDIA_TYPE: string = 'video';


function pushDefault(
    context: Array<Value | Segment> | undefined, 
    value: Value | Segment
): void {
    if (context === undefined) {
        context = [];
    }
    context.push(value);
}


export class Metrics {
    _segments: Array<Segment>;
    _droppedFrames: Array<Value>;
    _playerTime: Array<Value>;
    _bufferLevel: Array<Value>;

    constructor(raw_metrics?) {
        this.clear();
        if (raw_metrics !== undefined) {
            let segment = new Segment()
                .withStartTime(
                    raw_metrics.scheduling.startTime, 
                    raw_metrics.scheduling.duration)
                .withState(SEGMENT_STATE.LOADING)
                .withTimestamp(timestamp(raw_metrics.scheduling.t))
                .withQuality(raw_metrics.scheduling.quality);

            this.withSegment(segment);
            this.withDroppedFrames(new Value(raw_metrics.dropped.droppedFrames));
            this.withPlayerTime(new Value(Math.round(raw_metrics.info.time * 1000)));
            this.withBufferLevel(new Value(Math.round(raw_metrics.buffer_level * 1000)));
        }
    }

    _apply(
        builder: string, 
        array: Array<Segment | Value>, 
        filter?: (x: Segment | Value) => boolean,
    ): Metrics {
        if (filter !== undefined) {
            array = array.filter(filter);
        }
        for (let value of array) {
            this[builder](value);    
        }
        return this;
    }

    withMetrics(
        metrics: Metrics, 
        filter?: (x: Segment | Value) => boolean,
    ): Metrics {
        return this
            ._apply('withDroppedFrames', metrics.droppedFrames, filter)
            ._apply('withPlayerTime', metrics.playerTime, filter)
            ._apply('withBufferLevel', metrics.bufferLevel, filter)
            ._apply('withSegment', metrics.segments, filter);
    }
 
    clear(): Metrics {
        this._droppedFrames = [];
        this._bufferLevel = [];
        this._playerTime = [];
        this._segments = [];
        return this;
    }

    // Serialize metrics; if noProgress is true, then don't include the segment serialization
    serialize(noProgress: boolean = false): Json {
        // @ts-ignore: unsafe to use stringify, then JSON.parse
        const unique: (a: Array<Json>) => Array<Json> = arr => [...new Set(arr.map(stringify))].map(JSON.parse); 
        // @ts-ignore
        const transform: (a: Array<Segment | Value>) => Array<Json> = arr => unique(arr.map(x => x.serialize(noProgress)));
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
                let out: Array<Segment> = [];
                if (noProgress) {
                    return out;
                }
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

    // Sorts metrics by timestamp; mutates object.
    sorted(): Metrics {
        let cmp = (a, b) => a.timestamp - b.timestamp;
        this._droppedFrames.sort(cmp);
        this._playerTime.sort(cmp);
        this._bufferLevel.sort(cmp);
        this._segments.sort(cmp);
        return this;
    }

    withDroppedFrames(droppedFrames: Value): Metrics {
        this._droppedFrames.push(droppedFrames);
        return this;
    }

    withBufferLevel(bufferLevel: Value): Metrics {
        this._bufferLevel.push(bufferLevel);
        return this;
    }

    withPlayerTime(playerTime: Value): Metrics {
        this._playerTime.push(playerTime);
        return this;
    }

    withSegment(segment: Segment): Metrics {
        if (!isNaN(segment.index)) {
            this._segments.push(segment);
        }
        return this;
    }

    get segments(): Array<Segment> {
        return this._segments;
    }

    get bufferLevel(): Array<Value> {
        return this._bufferLevel;
    }

    get playerTime(): Array<Value> {
        return this._playerTime;
    }

    get droppedFrames(): Array<Value> {
        return this._droppedFrames;
    }
}


export class StatsTracker {
    player: ExternalDependency;
    callbacks: Array<(metrics: Metrics) => void>;
    
    constructor(player: ExternalDependency) {
        this.player = player;
        this.callbacks = [];
    }

    start() {
        this.getMetrics();
        setInterval(() => {
            this.getMetrics();
        }, TICK_INTERVAL_MS);
    }

    getMetrics(withCallbacks: boolean = true) {
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

    tick(metrics_wrapper: ExternalDependency): Metrics {
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
            'buffer_level' : execute(metrics_wrapper.getCurrentBufferLevel, MEDIA_TYPE),
        };
    
        let metrics = new Metrics(raw_metrics);
        return metrics;
    }

    registerCallback(callback: (metrics: Metrics) => void): void {
        this.callbacks.push(callback); 
    }
}
