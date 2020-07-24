#include "net/abrcc/abr/abr_minerva.h"

namespace quic { 

MinervaAbr::MinervaAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : SegmentProgressAbr(config) {}
MinervaAbr::~MinervaAbr() {}

int MinervaAbr::decideQuality(int index) { return 0; }
void MinervaAbr::registerAbort(const int index) {}
void MinervaAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics); 

  QUIC_LOG(WARNING) << "MINERVA METRICS\n";
}

abr_schema::Decision MinervaAbr::decide() {
  QUIC_LOG(WARNING) << "MINERVA STEP\n";
  
  // return noop
  return abr_schema::Decision();
}

}

