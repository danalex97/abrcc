export class ArgsParser {
    args: Array<string>;

    constructor(args: Array<string>) {
        this.args = args;
    }

    get serverSide() {
        return this.frontEnd === null;
    }

    get frontEnd(): string | null {
        for (let arg of this.args) {
            if (arg.includes('fe') || arg.includes('front-end')) {
                return arg.split('=')[1];
            }
        }
        return null;
    }

    get bola(): boolean {
        return this.frontEnd == 'bola';
    }

    get recordMetrics(): boolean {
        return this.args.includes('record')
            || this.args.includes('record-metrics');
    }

    get site(): string | null {
        for (let arg of this.args) {
            if (arg.includes('www')) {
                return arg;
            }
        }
        return null;
    }

    get metricsPort(): string | null {
        for (let arg of this.args) {
            if (arg.includes('metrics-port')) {
                return arg.split('=')[1];
            }
        }
        return null;
    }

    get quicPort(): string | null {
         for (let arg of this.args) {
            if (arg.includes('quic-port')) {
                return arg.split('=')[1];
            }
        }
        return null;
    }
}
