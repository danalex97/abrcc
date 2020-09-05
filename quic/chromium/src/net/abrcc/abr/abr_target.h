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

// TargetAbr -- basic implementation
class TargetAbr : public SegmentProgressAbr, public StateTracker {
 public:
  TargetAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~TargetAbr() override;
 
  void registerMetrics(const abr_schema::Metrics &) override;
 
  // Decides the quality for the current segment in a similar manner to RobustMpc
  // by assuming a safe bandwidth of (1 - alpha) min(E(b), b) for the current 
  // average bandwidth b(computed by BBR) and estimator `bw_estimator`.
  // 
  // It also computes the `bandwidth_target` value that is used in the adjustCC
  // function. The target represents the solution of the optimization problem:
  //    min b_t s.t.
  //      (1 - alpha) min(E(b), b) <= b_t <= (1 + alpha) max(E(b), b)
  //       QoE(k, b_t) >= beta QoE(k, (1 + alpha) max(E(b), b)
  // where E(b) is the bandwidth estimator `bw_estimator`.
  int decideQuality(int index) override;  
 
  // Computes the QoE for a segment given the `last_vmaf`, current segment's VMAF
  // `currnet_vmaf` and the `buffer` and `rebuffer` times(in ms).
  virtual double localQoe(int current_vmaf, int last_vmaf, int rebuffer, int buffer); 
 private:
  // Compute the VMAF for given segment `index` and `quality` . 
  // This is done using the given video `config`.
  int vmaf(const int quality, const int index);
  
  // For a given bandwidth, compute the pair (QoE, quality). The QoE is the approximatively 
  // best possible QoE over a long future horizon given the player mainatining the
  // `bandwidth` capacity. The `quality` value is the quality chosen for the current segment
  // (`decision_index`) to match the best approximate best QoE. The best QoE is an 
  // approximation as we use dynamic programming for estimating it over a large horizon.
  std::pair<double, int> qoe(const double bandwidth);

  // Callbacks for adjusting the CC's pacing cycle. The pacing cycle is adjusted based 
  // on the proportion of the current bandwidth value(provided by BBR) and the target
  // bandwidth computed in the decideQuality function.
  void adjustCC();

  // The bandwidth estimator is a different one than for WorthedAbr. We use a line fit 
  // estimator with (bandwidth, time) points when the time points are projected over 
  // TargetAbrConstants::time_delta units.
  std::unique_ptr<structs::MovingAverage<double>> bw_estimator;  

  // Bandwidth target compute for adjusting the congestion control in the decideQuality 
  // function. 
  int bandwidth_target;
  
  // Last bandwidth that was used for adjusting the pacing cycle in `adjustCC`.
  int last_adjustment_bandwidth;
};

// TargetAbr implementation that uses a different inferace for adjusting the congestion
// control bansed on the `bandwidth_target`. The implementation can be found in the 
// `abrcc/cc/target.cc` file, while the main modification of the BBR algorithm can be 
// found in the `BbrTarget::GetTargetCongestionWindow` function.
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

// TargetAbr3 is a TargetAbr2 modification that modified the `localQoe` to include the 
// current buffer in the optimization objective. That is, the function ties to minimize the 
// size of the buffer to a conent, hence trying to stop the optimization to getting stuck
// at local minima.
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
