import { App } from '../apps/app';
import { logging } from '../common/logger';


const logger = logging('App');


export class FrontEndApp extends App {
    constructor(player) {
        super(player);
    }

    start() {
        logger.log("Starting App.")
    }
}
