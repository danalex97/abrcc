#pragma once

#ifndef ABRCC_CC_SELECTOR_H_
#define ABRCC_CC_SELECTOR_H_

#include "base/memory/singleton.h"

#include "net/third_party/quiche/src/quic/core/quic_types.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/send_algorithm_interface.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_mutex.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

namespace quic {
class CCSelector {
 public: 
  virtual ~CCSelector();
  static CCSelector* GetInstance();

  CongestionControlType getCongestionControlType();
  void setCongestionControlType(const std::string& cc_type);
  
  SendAlgorithmInterface* getSendAlgorithmInterface();
  void setSendAlgorithmInterface(SendAlgorithmInterface* interface);
 
  bool getNoAdaptation(); 
 private:
  CCSelector(); 

  CongestionControlType type;
  SendAlgorithmInterface* interface;
  bool no_adaptation;
};

}

#pragma GCC diagnostic pop

#endif
