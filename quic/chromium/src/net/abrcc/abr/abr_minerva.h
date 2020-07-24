#ifndef ABRCC_ABR_ABR_MINERVA_H_
#define ABRCC_ABR_ABR_MINERVA_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// data structure deps
#include "net/abrcc/dash_config.h"

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/abr/abr_base.h"

namespace quic {

class MinervaAbr : public SegmentProgressAbr {
 public:
  MinervaAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~MinervaAbr() override;

  // We use the same interface as SegmentProgressAbr in order to be able to keep the
  // state management logic
  void registerMetrics(const abr_schema::Metrics &) override;
  void registerAbort(const int) override;
  abr_schema::Decision decide() override;
  int decideQuality(int index) override;
};

}

#endif
