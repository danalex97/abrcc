#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

#include "net/abrcc/dash_config.h"

#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/bbr_adapter.h"
#include "net/abrcc/cc/target.h"
#include "net/abrcc/service/schema.h"

#include "net/abrcc/structs/averages.h"

#include "net/abrcc/abr/abr_base.h"
#include "net/abrcc/abr/abr_worthed.h"

#include <unordered_map>


namespace quic {

class TargetAbr : public SegmentProgressAbr, public StateTracker {
 public:
  TargetAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~TargetAbr() override;
 
  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;  
 private:
  int vmaf(const int quality, const int index);
  std::pair<double, int> qoe(const double bandwidth);

  void adjustCC();

  std::unique_ptr<structs::MovingAverage<double>> bw_estimator;  

  int bandwidth_target;
  int last_adjustment_bandwidth;
};

class TargetAbr2 : public SegmentProgressAbr {
 public:
  TargetAbr2(const std::shared_ptr<DashBackendConfig>& config);
  ~TargetAbr2() override;
 
  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;  
 private:
  int vmaf(const int quality, const int index);
  std::pair<double, int> qoe(const double bandwidth);

  void adjustCC();

  std::unique_ptr<structs::MovingAverage<double>> bw_estimator;  

  int bandwidth_target;
  
  // StateTracker state
  BbrTarget::BbrInterface* interface; 

  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
  std::unique_ptr<structs::MovingAverage<double>> average_bandwidth;  

  base::Optional<abr_schema::Value> last_bandwidth;
  base::Optional<abr_schema::Value> last_rtt;
  int last_timestamp;
};

AbrInterface* getAbr(
  const std::string& abr_type, 
  const std::shared_ptr<DashBackendConfig>& config
);

}

#pragma GCC diagnostic pop


#endif
