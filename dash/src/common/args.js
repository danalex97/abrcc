export class ArgsParser {
    constructor(args) {
        this.args = args;
    }

    get serverSide() {
        return !this.frontEnd;
    }

    get frontEnd() {
        return this.args.includes('fe')
            || this.args.includes('front-end');
    }
}
