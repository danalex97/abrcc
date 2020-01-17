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

    get recordMetrics() {
        return this.args.includes('record')
            || this.args.includes('record-metrics');
    }

    get site() {
        for (let arg of this.args) {
            if (arg.includes('www')) {
                return arg;
            }
        }
        return null;
    }

    get metricsPort() {
         for (let arg of this.args) {
            if (arg.includes('metrics-port')) {
                return arg.split('=')[1];
            }
        }
        return null;
    }

    get quicPort() {
         for (let arg of this.args) {
            if (arg.includes('quic-port')) {
                return arg.split('=')[1];
            }
        }
        return null;
    }
}
