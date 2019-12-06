const loggers = {};

function hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
       hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return hash;
} 

function intToRGB(i){
    let c = (i & 0x00FFFFFF).toString(16).toUpperCase();
    return "00000".substring(0, 6 - c.length) + c;
}

export class Logger {
    constructor(logName) {
        this.logName = logName;
        this.color = intToRGB(hashCode(logName));
    }

    log() {
        let toLog = [
            `%c  ${this.logName}  `,
            `color: white; background-color: #${this.color}`,
        ];
        for (let argument of arguments) {
            toLog.push(" | "); 
            toLog.push(argument);
        }
        console.log(...toLog);
    }
}

export function logging(logName) {   
    if (loggers[logName] === undefined) {
        loggers[logName] = new Logger(logName);
    }
    return loggers[logName];
}
