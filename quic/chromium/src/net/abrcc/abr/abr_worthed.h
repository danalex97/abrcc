#ifndef ABRCC_ABR_ABR_WORTHED_H_
#define ABRCC_ABR_ABR_WORTHED_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// base abr algorithms
#include "net/abrcc/abr/abr_base.h"

// data structure deps
#include "net/abrcc/dash_config.h"
#include "net/abrcc/structs/averages.h"

#include <vector>

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/bbr_adapter.h"

namespace quic {

namespace StateTrackerConstants { 
  const int bandwidth_window = 10;
}


// Statistics Tracker for BBR-based CC algorithms(wrapped in BbrAdapter interface) that 
// allows for computing more useful metrics from the received front-end ones:
//   - last_player_time: the last player_time(ms) according to the timestamps
//   - last_buffer_level: the last buffer_level(ms) according to the timestamps
//   - average_bandwidth: EWMA bandwidth(kbps)
// 
//   - last_bandwdith: lastest timestamped bandwidth(kbps) estimation from BBR
//   - last_rtt: lastest timestamped RTT estimation(ms) from BBR 
//
class StateTracker {
 public:
  StateTracker(std::vector<int> bitrate_array);
  virtual ~StateTracker();

  void registerMetrics(const abr_schema::Metrics &);
 protected:
  BbrAdapter::BbrInterface* interface; 

  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
  std::unique_ptr<structs::MovingAverage<double>> average_bandwidth;  

  base::Optional<abr_schema::Value> last_bandwidth;
  base::Optional<abr_schema::Value> last_rtt;
 private:
  int last_timestamp;
  std::vector<int> _bitrate_array;
};

// WorthedAbr implementation.
class WorthedAbr : public SegmentProgressAbr, public StateTracker {
 public:
  WorthedAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~WorthedAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;
 private:
  // Compute reward(QoE for the future horizon) for a given set of future quality 
  // choices, and current state of the ABR(current start index, future minimum
  // bandwidth estimate, current buffer and current quality).
  double compute_reward(
    std::vector<int> qualities, 
    int start_index, 
    int bandwidth,
    int start_buffer,
    int current_quality
  );
  // Compute the optimum (reward, quality) pair given the current ABR state. The 
  // stochastic flag will explore only a part of the horizon for faster computations.
  std::pair<double, int> compute_reward_and_quality(
    int start_index, 
    int bandwidth,
    int start_buffer,
    int current_quality,
    bool stochastic,
    int last_decision
  );

  // Aggresivity computation functions: for a given bandwdith and delta, we compute the 
  // aggresivity factor by which the CC will be adjusted. 
  double partial_bw_safe(double bw);
  double factor(double bw, double delta);
  double aggresivity(double bw, double delta);
  
  // The adjusted buffer level is an adjustment of the current buffer level by the 
  // time proportion of the current segment being downloaded.
  int adjustedBufferLevel(int index);
 
  // Compute (rate_safe, rate_worthed) over the future horizion as follows:
  //  - rate_safe: a conservative estimate of the current available bandwidth
  //  - rate_worthed: a rate which obtains Delta more QoE than the QoE associated with 
  //                  rate_safe over the future horizon 
  std::pair<int, int> computeRates(bool stochastic);

  // Callbacks for adjusting the CC's pacing cycle. 
  void adjustCC(); 

  // Callback that can turn on or off the RTT probing functinality of BBR. When RTT probing
  // is turned on, BBR will only keep looping over the bandwidth probing functinality.
  void setRttProbing(bool probing);

  int ban;
  bool is_rtt_probing;
};

}

#pragma GCC diagnostic pop

#endif
