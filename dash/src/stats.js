const TICK_INTERVAL_MS = 500;
const MEDIA_TYPE = 'video';
const MAX_QUALITY = 5;


export class Value {
    constructor(value, timestamp) {
        this.value = value;
        this.timestamp = new Date().getTime();
    }

    withTimestamp(timestamp) {
        this.timestamp = timestamp;
        return this;
    }
}


export class Segment {
    constructor() {
        this.timestamp = new Date().getTime();
    }

    withTimestamp(timestamp) {
        this.timestamp = timestamp;
        return this;
    }

    withQuality(quality) {
        this.quality = quality;
        return this;
    }

    withState(state) {
        this.state = state;
        return this;
    }
   
    withIndex(startTime, duration) {
        this.index = Math.round(startTime / duration) - 1;
        return this;
    }

    // assumes format [domain]/video[quality]/[segment].[type]
    withUrl(url) {
        let split = url.split('/');
        
        let raw_quality = split[split.length - 2];
        let quality = parseInt(raw_quality.substring(5), 10); 
        
        let raw_segment = split[split.length - 1];
        let segment = parseInt(raw_segment.split('.')[0], 10);
    
        this.quality = MAX_QUALITY - quality + 1;
        this.index = segment;
        this.state = 'downloaded';
        
        return this;
    }
}


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
        this.buffer_level = new Value(raw_metrics.buffer_level)
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
    }

    start() {
        setInterval(() => {
            let metrics_wrapper = this.player.getDashMetrics();
            this.tick(metrics_wrapper);
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
        console.log(metrics);
    }
}
