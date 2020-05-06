#ifndef ABRCC_ABR_ABR_GAP_H_
#define ABRCC_ABR_ABR_GAP_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// dependencies on other abr algorithms
#include "net/abrcc/abr/abr_base.h" // SegmentProgressAbr

// data structure deps
#include "net/abrcc/dash_config.h"
#include "net/abrcc/structs/averages.h"

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/target.h" // BbrTarget::BbrInterface


namespace quic {

class GapAbr : public SegmentProgressAbr {
 public:
  GapAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~GapAbr() override;
 
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
};

}


#pragma GCC diagnostic pop

#endif
