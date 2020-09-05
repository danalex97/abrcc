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

/**
 * Serializable object that contains all front-end metrics:
 *   - number of dropped frames at each timestamp since last metrics update
 *   - the player time(in seconds) at each timestamp since last metrics update
 *   - the buffer level(in milliseconds) at each timestamp since last metrics update
 *   - the list of new segments(including their download state) since last metrics update 
 */
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

    /**
     * Builder-patter for adding new Metrics filtered by a filter applicable for 
     * timestamped values.
     */
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

    /**
     * Drop all metrics.
     */
    clear(): Metrics {
        this._droppedFrames = [];
        this._bufferLevel = [];
        this._playerTime = [];
        this._segments = [];
        return this;
    }

    /**
     * Serialize metrics; if noProgress is true, then don't include the segment serialization
     */
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

    /**
     * Sorts metrics by timestamp; mutating the current object.
     */
    sorted(): Metrics {
        let cmp = (a, b) => a.timestamp - b.timestamp;
        this._droppedFrames.sort(cmp);
        this._playerTime.sort(cmp);
        this._bufferLevel.sort(cmp);
        this._segments.sort(cmp);
        return this;
    }

    /**
     * Builder for adding a *single* dropped frames metric.
     */
    withDroppedFrames(droppedFrames: Value): Metrics {
        this._droppedFrames.push(droppedFrames);
        return this;
    }

    /**
     * Builder for adding a *single* buffer level value.
     */
    withBufferLevel(bufferLevel: Value): Metrics {
        this._bufferLevel.push(bufferLevel);
        return this;
    }

    /**
     * Builder for adding a *single* player time value.
     */
    withPlayerTime(playerTime: Value): Metrics {
        this._playerTime.push(playerTime);
        return this;
    }

    /**
     * Builder for adding a *single* segment; requires the segment index 
     * to be an integer number.
     */
    withSegment(segment: Segment): Metrics {
        if (!isNaN(segment.index)) {
            this._segments.push(segment);
        }
        return this;
    }

    /******************
     * Getters below. *
     ******************/
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

/**
 * Class used for allowing automatic Metrics updates.
 */
export class StatsTracker {
    player: ExternalDependency;
    callbacks: Array<(metrics: Metrics) => void>;
    
    constructor(player: ExternalDependency) {
        this.player = player;
        this.callbacks = [];
    }

    /**
     * Start the automatic metrics update. A tick will be made every TICK_INTERVAL_MS.
     */
    start() {
        this.getMetrics();
        setInterval(() => {
            this.getMetrics();
        }, TICK_INTERVAL_MS);
    }

    /**
     * The tracker updates the Metrics from the DASH player. In case the withCallbacks
     * flag is on, all metrics callbacks are apllied to the metrics object.
     *
     * The `getMetrics` function is exposed as we might want to call it explictly after significant
     * modifications of the DASH player(e.g. new segment request). The callbacks *mutate* the metrics.
     */
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

    /**
     * Internal function: the tick returns a single mutable metrics object.
     *
     * Given a *metrics_wrapper* provided by the DASH player's method `getDashMetrics`,
     * return a Metrics object.
     */
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

    /**
     * Register a callback to be called during each getMetrics method.
     */
    registerCallback(callback: (metrics: Metrics) => void): void {
        this.callbacks.push(callback); 
    }
}
