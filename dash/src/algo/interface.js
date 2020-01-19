// @abstract
export class AbrAlgorithm {
    constructor() {
        this.ctx = {
            'requests' : [],
        };
    }

    getDecision(metrics, index, timestamp) {
        throw new TypeError("not implemented error");
    }

    newRequest(ctx) {
        this.ctx.requests.push(ctx);
    }
}

// @abstract
export class MetricGetter {
    constructor() {
    }

    update(metrics, ctx) {
        throw new TypeError("not implemented error");
    }

    get value() {
        throw new TypeError("not implemented error");
    }
}

