export class VideoInfo {
    constructor(config) {
        // save the bitrates
        this.bitrates = [];
        for (let conf of config.video_paths) {
            this.bitrates.push(conf.quality);
        }
        this.bitrates.sort();

        // save video information
        this.info = {};
        for (let conf of config.video_paths) {
            this.info[conf.quality] = conf.info;
        }
    }

    get bitrateArray() {
        return this.bitrates;
    }
}
