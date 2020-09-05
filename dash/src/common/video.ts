import { Dict } from '../types';


/**
 * Metadata assciated with a Segment: 
 *  - start_time: start time of the segment in the video in seconds
 *  - VMAF: value between 0 and 100 representing the perceptual quality
 *  - size: size of the segment in bytes
 */
export class SegmentInfo {
    start_time: number;
    vmaf: number;
    size: number;

    constructor(obj: object) {
        if (
            obj["start_time"] === undefined ||
            obj["vmaf"] === undefined || 
            obj["size"] === undefined
        )  {
            throw new TypeError(`Wrong segment info format ${obj}`);
        }

        this.start_time = obj["start_time"];
        this.vmaf = obj["vmaf"];
        this.size = obj["size"];
    }
}


/**
 * Collection of video-level metadata:
 *  - the available segment bands
 *  - the segment info for each segment from each band
 */
export class VideoInfo {
    bitrates: Array<number>;  
    info: Dict<string, Array<SegmentInfo>>; 

    constructor(config) {
        // save the bitrates
        this.bitrates = [];
        for (let conf of config.video_paths) {
            this.bitrates.push(conf.quality);
        }
        this.bitrates.sort((a, b) => a - b);

        // save video information
        this.info = {};
        for (let conf of config.video_paths) {
            let segments: Array<SegmentInfo> = [];
            for (let raw_segment_info of conf.info) {
                segments.push(new SegmentInfo(raw_segment_info));
            }
            this.info[conf.quality] = segments;
        }
    }

    get bitrateArray(): Array<number> {
        return this.bitrates;
    }
}
