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
