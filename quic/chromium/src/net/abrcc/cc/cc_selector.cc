#include "net/abrcc/cc/cc_selector.h"
#include "net/abrcc/cc/singleton.h"

using namespace quic;
 
CCSelector* CCSelector::GetInstance() {
  return GET_SINGLETON(CCSelector);
}

CCSelector::CCSelector() : type(kBBR), interface(nullptr), no_adaptation(false) {}
CCSelector::~CCSelector() {}

CongestionControlType CCSelector::getCongestionControlType() {
  return type;
}

bool CCSelector::getNoAdaptation() {
  return no_adaptation;
}

void CCSelector::setCongestionControlType(const std::string& cc_type) {
  if (cc_type == "bbr") {
    type = kBBR;
  } else if (cc_type == "abbr") {
    type = kAbbr;
  } else if (cc_type == "xbbr") {
    type = kAbbr;
    no_adaptation = true;
  } else if (cc_type == "pcc") {
    type = kPCC;
  } else if (cc_type == "cubic") {
    type = kCubicBytes; 
  } else if (cc_type == "reno") {
    type = kRenoBytes;
  }
}

SendAlgorithmInterface* CCSelector::getSendAlgorithmInterface() {
  return interface;
}

void CCSelector::setSendAlgorithmInterface(SendAlgorithmInterface* interface) {
  this->interface = interface;
}
