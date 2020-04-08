function getReferenceTime() {
    if (window.referenceTimestamp === undefined) {
        window.referenceTimestamp = new Date().getTime();
    } else {
        return window.referenceTimestamp;
    }
}

export function timestamp(value) {
    let ref = getReferenceTime();
    if (value instanceof Date) {
        return Math.max(value.getTime() - ref, 0); 
    } else if (Number.isInteger(value) || !isNaN(parseFloat(value))) {
        return Math.max(value - ref, 0);
    } else {
        throw new TypeError(`[time.js] {value} has unknown type`)
    }
}

getReferenceTime()
