#include "net/abrcc/abr/abr_minerva.h"

#include <chrono>
using namespace std::chrono;

namespace quic { 

namespace MinervaConstants {
  const int updateIntervalFactor = 25; 
}

MinervaAbr::MinervaAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : SegmentProgressAbr(config)
  , interface(TcpMinervaSenderBytes::MinervaInterface::GetInstance())
  , timestamp_(high_resolution_clock::now()) 
  , update_interval_(base::nullopt) 
  , started_rate_update(false) {}
MinervaAbr::~MinervaAbr() {}

int MinervaAbr::decideQuality(int index) { return 0; }
void MinervaAbr::registerAbort(const int index) {}
void MinervaAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics); 

  QUIC_LOG(WARNING) << "MINERVA METRICS";
}

abr_schema::Decision MinervaAbr::decide() {
  if (updateIntervalMs() != base::nullopt) {
    if (update_interval_ == base::nullopt) {
      // we are at the first update interval
      update_interval_ = updateIntervalMs();
      timestamp_ = high_resolution_clock::now();
      
      // return noop directly
      return abr_schema::Decision();
    }
    
    auto current_time = high_resolution_clock::now();
    duration<double, std::milli> time_span = current_time - timestamp_;
  
    if (time_span.count() > update_interval_.value() / 2 && !started_rate_update) {
      // we are at the start of moment rate udpdate
      onStartRateUpdate();
      started_rate_update = true;
    }

    if (time_span.count() > update_interval_.value()) {
      // call the weight update function
      onWeightUpdate();
      started_rate_update = false;
    
      // update the update_interval_ based on newer min_rtt estimations
      update_interval_ = updateIntervalMs();
    }
  }

  // return noop
  return abr_schema::Decision();
}

// Returns the Minerva update time period as a function min_rtt 
base::Optional<int> MinervaAbr::updateIntervalMs() {
  auto min_rtt = interface->minRtt();
  if (min_rtt == base::nullopt) {
    return base::nullopt;
  }
  return min_rtt.value() * MinervaConstants::updateIntervalFactor; 
}

void MinervaAbr::onStartRateUpdate() {
  QUIC_LOG(WARNING) << "MINERVA ON START RATE UPDATE";
}

void MinervaAbr::onWeightUpdate() {
  QUIC_LOG(WARNING) << "MINERVA ON WEIGHT UPDATE";
}

}

