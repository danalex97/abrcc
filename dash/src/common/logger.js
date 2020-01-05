import { timestamp as create_timestamp } from '../common/time';


const loggers = {};
const central_log = new class {
    constructor() {
        this._log = [];
    }

    log(logname, args) {
        let timestamp = create_timestamp(new Date());
        let toLog = `[${logname}] ${timestamp}`;
        for (let arg of args) {
            toLog = toLog.concat(" | "); 
            if (typeof arg === 'string') {
                toLog = toLog.concat(arg);
            } else {
                toLog = toLog.concat(JSON.stringify(arg));
            }
        }
        this._log.push(toLog);
    }

    getLogs() {
        return [...this._log];
    }
}();


export function exportLogs() {
    return central_log.getLogs();
}


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
        central_log.log(this.logName, arguments);    
    }
}

export function logging(logName) {   
    if (loggers[logName] === undefined) {
        loggers[logName] = new Logger(logName);
    }
    return loggers[logName];
}
