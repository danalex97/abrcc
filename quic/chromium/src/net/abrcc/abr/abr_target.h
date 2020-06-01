#ifndef ABRCC_ABR_ABR_TARGET_H_
#define ABRCC_ABR_ABR_TARGET_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"


// dependencies on other abr algorithms
#include "net/abrcc/abr/abr_base.h" // SegmentProgressAbr
#include "net/abrcc/abr/abr_worthed.h" // StateTracker

// data structure deps
#include "net/abrcc/dash_config.h"
#include "net/abrcc/structs/averages.h"

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/target.h" // BbrTarget::BbrInterface


namespace quic {

class TargetAbr : public SegmentProgressAbr, public StateTracker {
 public:
  TargetAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~TargetAbr() override;
 
  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;  
 
  // rebuffer, buffer in ms
  virtual double localQoe(int current_vmaf, int last_vmaf, int rebuffer, int buffer); 
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
  
  // rebuffer, buffer in ms
  virtual double localQoe(int current_vmaf, int last_vmaf, int rebuffer, int buffer); 
 private:
  int vmaf(const int quality, const int index);
  std::pair<double, int> qoe(const double bandwidth);

  void adjustCC();

  std::unique_ptr<structs::MovingAverage<double>> bw_estimator;  
  int bandwidth_target;
  
  // StateTracker state -- start
  BbrTarget::BbrInterface* interface; 

  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
  std::unique_ptr<structs::MovingAverage<double>> average_bandwidth;  

  base::Optional<abr_schema::Value> last_bandwidth;
  base::Optional<abr_schema::Value> last_rtt;
  int last_timestamp;
  // StateTracker state -- end

  friend class GapAbr;
  friend class RemoteAbr;
};

class TargetAbr3 : public TargetAbr2 {
 public:
  TargetAbr3(const std::shared_ptr<DashBackendConfig>& config);
  ~TargetAbr3() override;
 
  // rebuffer, buffer in ms
  double localQoe(int current_vmaf, int last_vmaf, int rebuffer, int buffer) override; 
};

}


#pragma GCC diagnostic pop

#endif
