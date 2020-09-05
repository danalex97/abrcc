#ifndef ABRCC_ABR_ABR_GAP_H_
#define ABRCC_ABR_ABR_GAP_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// dependencies on other abr algorithms
#include "net/abrcc/abr/abr_target.h" // TargetAbr2

// data structure deps
#include "net/abrcc/dash_config.h"

// interfaces
#include "net/abrcc/abr/interface.h"

// interface of Gap CC
#include "net/abrcc/cc/gap.h"


namespace quic {

// GapAbr implementation based on TargetAbr2's QoE long horizon QoE computation 
// functions. The quality decision for the current segment is done in a similar manner
// to TargetAbr, with the only adjustments made to `target_bandwidth` computation.
class GapAbr : public TargetAbr2 {
 public:
  GapAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~GapAbr() override;
 
  void registerMetrics(const abr_schema::Metrics &metrics) override;
  
  // Decides the quality for the current segment in a similar manner to RobustMpc
  // by assuming a safe bandwidth of (1 - alpha) min(E(b), b) for the current 
  // average bandwidth b(computed by BBR) and estimator `bw_estimator`.
  // 
  // It also computes the bandwidth target value that is passed to the `interface`
  // and `gap_interface` interfaces in the setTarget function. The target represents 
  // the solution of the optimization problem:
  //    min b_t s.t.
  //      (1 - alpha) min(E(b), b) <= b_t <= max(T_bw, (1 + alpha) max(E(b), b))
  //       QoE(k, b_t) >= beta QoE(k, (1 + alpha) max(E(b), b)
  // where E(b) is the bandwidth estimator `bw_estimator` and `T_bw` is the average
  // needed bandwidth for downloading a few segments after a local minimum over a H
  // future window. 
  // 
  // Furthremore, the b_t value is adjusted by modifying the beta parameter(
  // `final_qoe_pecentile`) invertly proportional to the gain defined by:
  //     gain = (T_bw - (1 - alpha) min(E(b), b)) / (1 - alpha) min(E(b), b)
  int decideQuality(int index) override;  
 
 private:
  // We use both BbrTarget::BbrInterface and BbrGap::gap_interface since we want
  // to allow both CC operation modes.
  BbrGap::BbrInterface* gap_interface; 
};

}


#pragma GCC diagnostic pop

#endif
