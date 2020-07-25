#ifndef ABRCC_ABR_ABR_MINERVA_H_
#define ABRCC_ABR_ABR_MINERVA_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// data structure deps
#include "net/abrcc/dash_config.h"

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/abr/abr_base.h"
#include "net/abrcc/cc/minerva.h"

// timestamps
#include <chrono>

// utilities
#include <deque>

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
 
 private:
  // computes a conservative rate measurement
  int conservativeRate() const;
  
  // return the update interval in ms as measured currently
  base::Optional<int> updateIntervalMs();
  
  // callbacks for update rates
  void onStartRateUpdate();
  void onWeightUpdate();

  MinervaInterface* interface; 

  std::chrono::high_resolution_clock::time_point timestamp_;
  base::Optional<int> update_interval_;
  bool started_rate_update;

  // rate computation variables
  std::deque<int> past_rates;
  double moving_average_rate;
};

}

#endif
