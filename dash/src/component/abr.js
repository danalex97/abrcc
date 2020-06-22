import { logging } from '../common/logger'; 


const logger = logging('abr');
const abandon_logger = logging('abandon');
const dash_logger = logging('DashLog');
const MEDIA_TYPE = 'video';


export function getFactory() {
    return window.dashjs.FactoryMaker;
}

function getQualityController() {
    return window.qualityController;
}

export function SetQualityController(qualityController) {
    window.qualityController = qualityController;
}

function setPlayer(player) {
    window.player = player;   
}

function getPlayer() {
    return window.player;
}

(function(){
    window._onText = (args) => {};
    window._onEventContext = {};
    let originallog = console.info;

    let handler = function() {
        window._onText(Array.from(arguments));
        dash_logger.log(...arguments);
    };
    console.info = handler;
    console.warn = handler;
})();

export function onEvent(event, callback) {
    let oldOntext = window._onText;
    window._onText = (args) => {
        if (args.some(arg => arg.includes && arg.includes(event))) {
            callback(Object.assign(window._onEventContext, {
                'args' : args,
            }));
        }
        oldOntext(args);
    }
}

function initScheduleController(context) {
    context.streamController.getActiveStreamProcessors().forEach(streamProcessor => {
        context.scheduleController = streamProcessor.getScheduleController();
    });
}

function ServerSideRuleClass() {
    let factory = getFactory();
    let context = window._onEventContext;

    const SwitchRequest    = factory.getClassFactoryByName('SwitchRequest');
    const MetricsModel     = factory.getSingletonFactoryByName('MetricsModel');
    const StreamController = factory.getSingletonFactoryByName('StreamController');
    
    let instance;
    let factoryCtx = this.context;

    context.player = getPlayer();
    context.streamController = StreamController(factoryCtx).getInstance();
    context.scheduleController = undefined;

    initScheduleController(context);

    function getMaxIndex(rulesContext) {
        let streamController = context.streamController;
        let abrController = rulesContext.getAbrController();
        let current = abrController.getQualityFor(MEDIA_TYPE, streamController.getActiveStreamInfo());

        let quality = getQualityController().getQuality(undefined, current);
        logger.log("Quality change", quality);
        if (current === quality) {
            return SwitchRequest(factoryCtx).create();
        }

        let switchRequest = SwitchRequest(factoryCtx).create();
        switchRequest.quality = quality;
        switchRequest.reason = 'New rate received';
        switchRequest.priority = SwitchRequest.PRIORITY.STRONG;
        return switchRequest;
    }

    function shouldAbandon(rulesContext) {
        const switchRequest = SwitchRequest(factoryCtx).create(
            SwitchRequest.NO_CHANGE, {}
        );

        const mediaInfo = rulesContext.getMediaInfo();
        const mediaType = rulesContext.getMediaType();
        const req = rulesContext.getCurrentRequest();
        const index = req.index;
        
        let metricsModel = MetricsModel(factoryCtx).getInstance();
        let dashMetrics = metricsModel.getMetricsFor(mediaType, true);
       
        // if the request was made
        if (!isNaN(index)) {
            // get buffer level
            let bufferLevel = 10000;
            if (dashMetrics.BufferLevel && dashMetrics.BufferLevel.length > 0) {
                bufferLevel = dashMetrics.BufferLevel[dashMetrics.BufferLevel.length - 1].level;
            }
            const minBufferLevel = 2000;
            const minIndex = 5;

            // if buffer level is below our limit and we passed startup
            if (bufferLevel < minBufferLevel && index >= minIndex) {
                abandon_logger.log(`Buffer level ${bufferLevel} under ${minBufferLevel}.`);
                abandon_logger.log("Possible rebuffer detected");
                
                // [TODO] need to contact backend to ensure we switch to recovery ABR state 
                // [TODO]  -- how do we do the re-request?
                // [TODO] need to do switchRequest again 
            }
        }
        return switchRequest;
    }

    instance = {
        getMaxIndex: getMaxIndex,
        shouldAbandon: shouldAbandon,
    };

    return instance;
}

export function GetServerSideRule(player) {
    setPlayer(player);

    ServerSideRuleClass.__dashjs_factory_name = 'ServerSideRule';
    return getFactory().getClassFactory(ServerSideRuleClass);
}

