import { logging } from '../common/logger'; 


const logger = logging('abr');
const MEDIA_TYPE = 'video';


function getFactory() {
    return window.dashjs.FactoryMaker;
}

function getQualityController() {
    return window.qualityController;
}

export function SetQualityController(qualityController) {
    window.qualityController = qualityController;
}

function ServerSideRuleClass() {
    let factory = getFactory();

    let SwitchRequest = factory.getClassFactoryByName('SwitchRequest');
    let MetricsModel = factory.getSingletonFactoryByName('MetricsModel');
    let StreamController = factory.getSingletonFactoryByName('StreamController');
    let context = this.context;
    let instance;

    function setup() {
    }

    function getMaxIndex(rulesContext) {
        let streamController = StreamController(context).getInstance();
        let abrController = rulesContext.getAbrController();
        let current = abrController.getQualityFor(MEDIA_TYPE, streamController.getActiveStreamInfo());

        let metricsModel = MetricsModel(context).getInstance();
        let metrics = metricsModel.getMetricsFor('video', true);
        logger.log(metrics);

        logger.log("new request");
        let quality = getQualityController().getQuality();
        if (current === quality) {
            return SwitchRequest(context).create();
        }

        let switchRequest = SwitchRequest(context).create();
        switchRequest.quality = quality;
        switchRequest.reason = 'New rate received';
        switchRequest.priority = SwitchRequest.PRIORITY.STRONG;
        return switchRequest;
    }

    instance = {
        getMaxIndex: getMaxIndex
    };

    setup();

    return instance;
}

export function GetServerSideRule() {
    ServerSideRuleClass.__dashjs_factory_name = 'ServerSideRule';
    return getFactory().getClassFactory(ServerSideRuleClass);
}

