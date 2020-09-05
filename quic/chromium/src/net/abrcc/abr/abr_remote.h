#ifndef ABRCC_ABR_ABR_REMOTE_H_
#define ABRCC_ABR_ABR_REMOTE_H_

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

// ABR algorithm that externalizes the computation for target to a HTTP server.
// The used congestion control backend can be either Target(`abrcc/cc/target`) 
// or Gap(`abrcc/cc/gap`).
class RemoteAbr : public TargetAbr2 {
 public:
  RemoteAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~RemoteAbr() override;

  void registerMetrics(const abr_schema::Metrics &metrics) override;
  int decideQuality(int index) override;  
 private:
  // Given the current state of the ABR:
  //   - avg_bandwidth: average bandwidth computed using a Wilder Moving Average 
  //   - currnet_bandwidth: the latest bandwidth as measured by BBR
  //   - last_buffer: the buffer with the biggest timestamp 
  //   - last_rtt: the latest RTT as measured by BBR
  //   - current_quality: the quality for `current_index` - 1 
  //   - current_index: the index to decide the quality for
  //   - vmafs: the matrix of per-segment VMAFs for each quality band
  //   - sizes: the matrix of per-segment sizes for each quality band
  // Makes a request to the localhost at the fixed port RemosteAbrConstants::remote_port
  // exposing the full ABR state and asking for a `target_bandwidth` value. The target 
  // value will be passed to the CC backend. 
  int getTargetDecision(
    int avg_bandwidth,
    int current_bandwidth,
    int last_buffer,
    int last_rtt,
    int current_quality,
    int current_index,
    std::vector< std::vector<int> > vmafs,
    std::vector< std::vector<int> > sizes
  ); 

  // We use both BbrTarget::BbrInterface and BbrGap::gap_interface since we want
  // to allow both CC operation modes.
  BbrGap::BbrInterface* gap_interface; 
};

}


#pragma GCC diagnostic pop

#endif
