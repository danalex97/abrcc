declare global {
    interface Window { 
        referenceTimestamp: number; 
    }
}

function getReferenceTime(): number {
    if (window.referenceTimestamp === undefined) {
        window.referenceTimestamp = new Date().getTime();
    } 
    return window.referenceTimestamp;
}

/**
 * Create a timestamp from a `number` or `date`. The timestamp will be a float amount of 
 * seconds in reference to the reference time attached on the window at the invocation of the
 * Javascript code present in this file.
 */
export function timestamp(value: number | Date): number {
    let ref = getReferenceTime();
    if (value instanceof Date) {
        return Math.max(value.getTime() - ref, 0); 
    } else if (typeof value === 'number') {
        return Math.max(value - ref, 0);
    } else {
        throw new TypeError(`[time.js] {value} has unknown type`)
    }
}

getReferenceTime();
