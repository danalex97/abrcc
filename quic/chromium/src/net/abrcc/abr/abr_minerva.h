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

// Minerva implementation based on paper:
//   http://web.cs.ucla.edu/~ravi/CS219_F19/papers/minerva.pdf
class MinervaAbr : public AbrInterface {
 public:
  MinervaAbr(
    const std::shared_ptr<DashBackendConfig>& config,
    const std::string& minerva_config_path_,
    const bool normalize_
  );
  ~MinervaAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  void registerAbort(const int) override;
  abr_schema::Decision decide() override;
 
  std::vector< std::vector<VideoInfo> > segments;
  std::vector<int> bitrate_array;
 private:
  // Compute normalization map when Minerva is initialized. The normalization map 
  // is a bitarte-perceptual quality mapping computed based on a set of configuration 
  // files located at the `conf_path_`. The mapping is computed by the avearge perceptual 
  // quality(VMAF) interpolation associated with each segment given a particular rate 
  // of transmission. This is a way of computing a normalization function that can be used 
  // to adjust Minerva's behavior when competing with background TCP traffic as explained 
  // in the paper section 5.4.
  void computeNormalizationMap(const std::string& conf_path_);
  
  // Normalization function that maps a pecetual quality to a rate.
  double normalize(const double pq) const;

  // Computes a conservative rate measurement according to the `Rate Measurement` 
  // subsection of paper section 6. Specifically, it returns max(.8 current_rate, 
  // current_rate - .5 variance) where the current_rate is measured as the acked packets
  // over minRtt/2 while the variance is the variance of the last 4 current rate 
  // measurements made at distances of minRtt to each other.
  int conservativeRate() const;
 
  // Returns the update interval for the congestion control as a function of the 
  // minimum measured RTT. The paper uses 25 * minRtt as the interval. 
  base::Optional<int> updateIntervalMs();
 
  // Compute the utility for the current rate as explained in the paper section 5.3,
  // The utility function is a weighted average combination of the past QoE, 
  // current QoE and a value function computing the expected per-chunk QoE over the 
  // future horizon. All of the values are adjusted in accordance to the 
  // `moving_average_rate`.
  double computeUtility();

  // Callback for rate updates. The `onStartRateUpdate` callback is made at half the 
  // update interval, while the weightUpdate is done every update interval.
  //
  // At every weightUpdate, we adjust the past rates, the update interval and the computed
  // weight of the flow. The weight is computed as the report between the current moving 
  // average rate and the utility. The weight is passed directly to the adjusted Cubic
  // congestion control from the files `abrcc/cc/minerva`. The only adjustment to the 
  // Cubic function is done in the function `MinervaBytes::Beta` which uses the weight
  // adjusted beta computed in the function `MinervaBytes::WeightAdjustedBeta` according 
  // to the paper section 5.6.
  void onStartRateUpdate();
  void onWeightUpdate();
  
  MinervaInterface* interface; 

  std::chrono::high_resolution_clock::time_point timestamp_;
  base::Optional<int> update_interval_;
  bool started_rate_update;

  // Flags
  bool should_normalize;

  // Normalization function computed in the computeNormalizationMap function at 
  // Minerva initialization.
  std::vector<double> norm; 
  
  // Deque of the past measured rates. Each rate is measured as the size of acked bytes
  // over half of the update interval. The `past_rates` measurements are updated 
  // every update interval.
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
