import { Dict } from '../types';


export class SegmentInfo {
    start_time: number;
    vmaf: number;
    size: number;

    constructor(obj: object) {
        this.start_time = obj["start_time"];
        this.vmaf = obj["vmaf"];
        this.size = obj["size"];
    }
}


export class VideoInfo {
    bitrates: Array<number>;  
    info: Dict<string, SegmentInfo>; 

    constructor(config) {
        console.log("WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWEEEEEEEEEEEEEEEEEEEEEEEEE");
        
        // save the bitrates
        this.bitrates = [];
        for (let conf of config.video_paths) {
            this.bitrates.push(conf.quality);
        }
        this.bitrates.sort((a, b) => a - b);

        // save video information
        this.info = {};
        for (let conf of config.video_paths) {
            this.info[conf.quality] = new SegmentInfo(conf.info);
        }
    }

    get bitrateArray() {
        return this.bitrates;
    }
}
