import { logging } from '../common/logger'; 

/**
 * WARNING: Here be dragons
 */

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

function setShim(shim) {
    window.shim = shim;   
}

function getShim() {
    return window.shim;
}

function setInterceptor(interceptor) {
    window.interceptor = interceptor;
}

function getInterceptor() {
    return window.interceptor;
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
        context.streamProcessor = streamProcessor;
    });
}

/**
 * ServerSideRuleClass factory.
 *
 * Exposes:
 *  - getMaxIndex: returns a SwitchRequest by which the DASH player will change the requested quality
 *  - shouldAbandon: return a SwitchRequest to the lowest quality if the backend decides to 
 *      drop the current segment transfer; to be able to do so, we use the internal state of the 
 *      interceptor
 *
 * The *getMaxIndex* does quality changes in accordance to the state of the QualityController. 
 */
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
    context.streamProcessor = undefined;

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

    let rebuffers = new Set();
    let lastRecoveryIndex = 0;

    function shouldAbandon(rulesContext) {
        let switchRequest = SwitchRequest(factoryCtx).create(
            SwitchRequest.NO_CHANGE, {}
        );

        const mediaInfo = rulesContext.getMediaInfo();
        const mediaType = rulesContext.getMediaType();
        const req = rulesContext.getCurrentRequest();
        const index = req.index;

        let metricsModel = MetricsModel(factoryCtx).getInstance();
        let dashMetrics = metricsModel.getMetricsFor(mediaType, true);
        const recoveryCooldown = 2; // in number of segments
        const minIndex = 5; // minimum index for checking small buffer
        const minBufferLevel = 3500;
   
        // obtain the context variables
        const interceptor = getInterceptor();
        const shim = getShim();
        const videoLength = interceptor.videoLength;


        // if the request was made
        if (!isNaN(index)) {
            // get buffer level
            let bufferLevel = 10000;
            if (dashMetrics.BufferLevel && dashMetrics.BufferLevel.length > 0) {
                bufferLevel = dashMetrics.BufferLevel[dashMetrics.BufferLevel.length - 1].level;
            }

            // if buffer level is below our limit and we passed startup
            if (bufferLevel < minBufferLevel && 
                index >= minIndex && 
                !rebuffers.has(index) && 
                index > lastRecoveryIndex + recoveryCooldown && 
                index < videoLength - 1 
            ) {
                // add to rebuffer set, so we don't call the recovery more times
                rebuffers.add(index);
                
                abandon_logger.log(`Buffer level ${bufferLevel} under ${minBufferLevel}.`);
                abandon_logger.log("Possible rebuffer detected");
               
                // switch to lowest quality if that's not the case yet
                if (getQualityController().getQuality(index + 1, 1) > 0) {
                    let abrXmlRequest = interceptor._toIntercept[index + 1]["ctx"];
                    const makeWritable = interceptor._toIntercept[index + 1]["makeWritable"];
                    const execute = interceptor._toIntercept[index + 1]["execute"];
                    const newEvent = interceptor._toIntercept[index + 1]["newEvent"];
                    
                    let backendXmlRequest = interceptor.context(index + 1)['xmlRequest'];
                    let backendRequest = interceptor.context(index + 1)['requestObject'];
                    abandon_logger.log('Real req', backendXmlRequest);
                    if (backendXmlRequest.readyState != 4) {
                        // update lastRecoveryIndex
                        lastRecoveryIndex = index;
                        
                        // abort the backend request
                        backendXmlRequest.abort();
                        
                        // tell backend to abort request
                        shim.abortRequest()
                            .addIndex(index + 1)
                            .send();
                        
                        // set bypass in interceptor for newly generated request 
                        abandon_logger.log('Setting bypass for: ', index + 1);
                        interceptor.setBypass(index + 1);
                                    
                        // abort old request
                        abrXmlRequest.abort();
                        execute(abrXmlRequest.onabort, new Event('abort'));
                            
                        // Create the switch request
                        switchRequest.quality = 0;
                        switchRequest.reason = "Rebuff detected";                       
                        abandon_logger.log("Switch request", switchRequest);
                    }
                    return switchRequest;
                }
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

/**
 * Crate a ServerSideRule, given:
 *   - player: the DASH player
 *   - shim: a backend shim used for allowing backend requests
 *   - intercetor: interceptor class exposed for XMLHttp request interception
 *
 * The *shim* and *interceptor* are exposed so that in case of abandoned segments, we can interact 
 * with the actual backend requests, rather than the XMLHttp objects modified by the intercetor.
 *
 * The *player* is exposed to allow the player to stall in case a backend-decision is yet to arrive.
 */ 
export function GetServerSideRule(player, shim, interceptor) {
    setPlayer(player);
    setShim(shim);
    setInterceptor(interceptor);

    ServerSideRuleClass.__dashjs_factory_name = 'ServerSideRule';
    return getFactory().getClassFactory(ServerSideRuleClass);
}

