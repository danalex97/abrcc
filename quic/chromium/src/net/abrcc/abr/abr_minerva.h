#ifndef ABRCC_ABR_ABR_MINERVA_H_
#define ABRCC_ABR_ABR_MINERVA_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// data structure deps
#include "net/abrcc/dash_config.h"

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/minerva.h"

// timestamps
#include <chrono>

// utilities
#include <deque>
#include <unordered_map>
#include <unordered_set>
#include <vector>


namespace quic {

class MinervaAbr : public AbrInterface {
 public:
  MinervaAbr(
    const std::shared_ptr<DashBackendConfig>& config,
    const std::string& minerva_config_path_
  );
  ~MinervaAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  void registerAbort(const int) override;
  abr_schema::Decision decide() override;
 
  std::vector< std::vector<VideoInfo> > segments;
  std::vector<int> bitrate_array;
 private:
  // compute normalization map when Minerva is initialized
  void computeNormalizationMap(const std::string& conf_path_);
  double normalize(const double pq) const;

  // computes a conservative rate measurement
  int conservativeRate() const;
  
  // returns the update interval in ms as measured currently
  base::Optional<int> updateIntervalMs();
 
  // compute the utility for the current rate
  double computeUtility();

  // callbacks for update rates
  void onStartRateUpdate();
  void onWeightUpdate();
  
  MinervaInterface* interface; 

  std::chrono::high_resolution_clock::time_point timestamp_;
  base::Optional<int> update_interval_;
  bool started_rate_update;

  // normalization function
  std::vector<double> norm; 
  
  // rate computation variables
  std::deque<int> past_rates;
  double moving_average_rate;

  // front-end state
  std::unordered_map<int, abr_schema::Segment> last_segment;  
  int last_index;
  int last_timestamp;
  int last_quality;
  abr_schema::Value last_buffer; 
};

}

#endif
