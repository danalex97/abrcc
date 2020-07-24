#include "net/abrcc/abr/abr_minerva.h"

#include <chrono>
using namespace std::chrono;

namespace quic { 

namespace MintervaConstants {
  const int updateIntervalFactor = 25; 
}

MinervaAbr::MinervaAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : SegmentProgressAbr(config)
  , interface(TcpMinervaSenderBytes::MinervaInterface::GetInstance())
  , timestamp_(high_resolution_clock::now()) {}
MinervaAbr::~MinervaAbr() {}

int MinervaAbr::decideQuality(int index) { return 0; }
void MinervaAbr::registerAbort(const int index) {}
void MinervaAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics); 

  QUIC_LOG(WARNING) << "MINERVA METRICS";
}

abr_schema::Decision MinervaAbr::decide() {
  if (updateIntervalMs() != base::nullopt) {
    auto current_time = high_resolution_clock::now();
    duration<double, std::milli> time_span = current_time - timestamp_;
  
    if (time_span.count() > updateIntervalMs()) {
      // at our first tick after updateIntervalMs(), call the update function
      onUpdate();
      timestamp_ = current_time;
    }
  }

  // return noop
  return abr_schema::Decision();
}

// Returns the Minerva update time period  
base::Optional<int> MinervaAbr::updateIntervalMs() {
  auto min_rtt = interface->minRtt();
  if (min_rtt == base::nullopt) {
    return base::nullopt;
  }
  return min_rtt.value() * MintervaConstants::updateIntervalFactor; 
}

void MinervaAbr::onUpdate() {
  QUIC_LOG(WARNING) << "MINERVA ON UPDATE";
}

}

