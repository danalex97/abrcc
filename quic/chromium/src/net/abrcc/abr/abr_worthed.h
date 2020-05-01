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

class WorthedAbr : public SegmentProgressAbr, public StateTracker {
 public:
  WorthedAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~WorthedAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;
 private:
  // reward computation
  double compute_reward(
    std::vector<int> qualities, 
    int start_index, 
    int bandwidth,
    int start_buffer,
    int current_quality
  );
  std::pair<double, int> compute_reward_and_quality(
    int start_index, 
    int bandwidth,
    int start_buffer,
    int current_quality,
    bool stochastic,
    int last_decision
  );

  // aggresivity
  double partial_bw_safe(double bw);
  double factor(double bw, double delta);
  double aggresivity(double bw, double delta);
  
  // utilities
  int adjustedBufferLevel(int index);
  
  std::pair<int, int> computeRates(bool stochastic);
  void adjustCC(); 
  void setRttProbing(bool probing);

  int ban;
  bool is_rtt_probing;
};

}

#pragma GCC diagnostic pop

#endif
