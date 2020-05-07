#include "net/abrcc/abr/abr_target.h"

// interface dependencies 
#include "net/abrcc/dash_config.h"
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

// data struct dependecies
#include "net/abrcc/structs/estimators.h" // LineFitEstimator

#include <algorithm>
#include <iostream>
#include <limits>
#include <fstream>
#include <unordered_map>
#include <unordered_set>
#include <functional>

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-const-variable"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"

namespace {
  const int SECOND = 1000; 
}

namespace quic {

/**
 * TargetAbr - begin
 **/

namespace TargetAbrConstants { 
  const int horizon = 10;  

  // constants used for QoE function weights
  const double alpha = 1.;
  const double beta = 2.5; 
  const double gamma = 100.; 
  const double zetta = 2. * gamma / horizon;

  // constants for bandwidth estimator
  const int bandwidth_window = 6;
  const int projection_window = 2;
  const int time_delta = 100;

  // constants for optimization objective
  const double qoe_percentile = .95;
  const double qoe_delta = .15;
  const int step = 100;
  
  // constants for deciding quality
  const double safe_downscale = .8;
}

TargetAbr::TargetAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : SegmentProgressAbr(config) 
  , StateTracker(bitrate_array)
  , bw_estimator(new structs::LineFitEstimator<double>(
      TargetAbrConstants::bandwidth_window,
      TargetAbrConstants::time_delta,
      TargetAbrConstants::projection_window
    ))
  , bandwidth_target(bitrate_array[0]) {} 


TargetAbr::~TargetAbr() {}

int TargetAbr::vmaf(const int quality, const int index) {
  return segments[quality][index].vmaf;
}

namespace {
  struct state_t {
    state_t() {
      this->segment = -1;
      this->buffer = -1;
      this->quality = -1;
    }
  
    state_t(int segment, int buffer, int quality) {
      this->segment = segment;
      this->buffer = buffer;
      this->quality = quality;
    }

    int segment;
    int buffer;
    int quality;
  
    bool operator == (const state_t &other) const {
      return segment == other.segment && buffer == other.buffer;
    }

    bool operator != (const state_t &other) const {
      return !(*this == other);
    }

    void operator = (const state_t &other) { 
      this->segment = other.segment;
      this->buffer = other.buffer;
      this->quality = other.quality;
    }

    friend std::ostream& operator << (std::ostream &os, const state_t &value);
  };

  struct value_t {
    value_t() {
    }

    value_t(int qoe, int vmaf, state_t from) {
      this->qoe = qoe;
      this->vmaf = vmaf;
      this->from = from;
    }

    int qoe; // [TODO] should this be double? 
    int vmaf;
    state_t from; 

    void operator = (const value_t& other) { 
      this->qoe = other.qoe;
      this->vmaf = other.vmaf;
      this->from = other.from;
    }

    friend std::ostream& operator << (std::ostream &os, const value_t &value);
  };
 
  std::ostream& operator << (std::ostream &os, const state_t &value) { 
    return os << "state_t(segment: " << value.segment << ", quality: " 
              << value.quality << ", buffer: " << value.buffer << ")";
  }
    
  std::ostream& operator << (std::ostream &os, const value_t &value) { 
    return os << "value_t(qoe: " << value.qoe << ", vmaf: " << value.vmaf 
              << ", from: " << value.from << ")";
  }
}

static int get_segment_length_ms(
  const std::vector< std::vector<VideoInfo> >& segments,
  const int current_index,
  const int chunk_quality
) {
  // [TODO] should we use current_index or current_index + 1?
  int ref_index = current_index + 1;
  while (ref_index + 1 >= int(segments[chunk_quality].size())) {
    ref_index--;
  }
  int segment_length_ms = int(double(::SECOND) * 
    (segments[chunk_quality][ref_index + 1].start_time 
    - segments[chunk_quality][ref_index].start_time)
  );
  return segment_length_ms;
}

double TargetAbr::localQoe(int current_vmaf, int last_vmaf, int rebuffer, int buffer) {
  return 1. * TargetAbrConstants::alpha * current_vmaf
    - 1. * TargetAbrConstants::beta * fabs(current_vmaf - last_vmaf)
    - 1. * TargetAbrConstants::gamma * rebuffer / ::SECOND;
}

std::pair<double, int> TargetAbr::qoe(const double bandwidth) {
  // compute current_vmaf, start_index, start_buffer
  int last_index = this->decision_index - 1; 
  int current_quality = decisions[last_index].quality;
  int current_vmaf = TargetAbr::vmaf(current_quality, last_index); 
  int start_index = last_index + 1;
  int start_buffer = last_buffer_level.value;
  
  // DP
  std::function<size_t (const state_t &)> hash = [](const state_t& state) {
    size_t seed = 0;
    seed ^= std::hash<int>()(state.segment) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    seed ^= std::hash<int>()(state.buffer) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    seed ^= std::hash<int>()(state.quality) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    return seed;
  };
  std::unordered_map<state_t, value_t, std::function<size_t (const state_t&)> > dp(0, hash);
  std::unordered_set<state_t, std::function<size_t (const state_t&)> > curr_states(0, hash);
  
  int buffer_unit = 40;
  int max_buffer = 100 * ::SECOND / buffer_unit;
  state_t null_state, start_state(last_index, start_buffer / buffer_unit, current_quality);
  dp[start_state] = value_t(0, current_vmaf, null_state);
  curr_states.insert(start_state);
 
  int max_segment = 0;
  for (int current_index = last_index; current_index < start_index + TargetAbrConstants::horizon; ++current_index) {
    if (current_index + 2 >= int(segments[0].size())) {
      continue;  
    }

    std::unordered_set<state_t, std::function<size_t (const state_t&)> > next_states(0, hash);
    for (auto &from : curr_states) {
      int max_quality = std::min(int(segments.size()) - 1, from.quality + 1);
      int min_quality = std::max(0, from.quality - 2);
      for (int chunk_quality = min_quality; chunk_quality <= max_quality; ++chunk_quality) {
        double current_buffer = from.buffer * buffer_unit;
        double rebuffer = 0;
        
        double size_kb = 8. * segments[chunk_quality][current_index + 1].size / ::SECOND;
        double download_time_ms = size_kb / bandwidth * ::SECOND;

        // simulate buffer changes
        if (current_buffer < download_time_ms) {
          rebuffer = download_time_ms - current_buffer;
          current_buffer = 0;
        } else {
          current_buffer -= download_time_ms;
        }

        int segment_length_ms = get_segment_length_ms(segments, current_index, chunk_quality);
        current_buffer += segment_length_ms;
        current_buffer = std::min(current_buffer, 1. * max_buffer * buffer_unit);

        // compute next state
        state_t next(current_index + 1, current_buffer / buffer_unit, chunk_quality);

        // compute current and last vmaf
        int current_vmaf = TargetAbr::vmaf(chunk_quality, current_index + 1);
        int last_vmaf    = dp[from].vmaf;
        
        // compute qoe
        double qoe = dp[from].qoe + localQoe(current_vmaf, last_vmaf, rebuffer, current_buffer);
        
        // update dp value with maximum qoe
        if (dp.find(next) == dp.end() || dp[next].qoe < qoe) {
          dp[next] = value_t(qoe, current_vmaf, from); 
          next_states.insert(next);

          max_segment = std::max(max_segment, current_index + 1);
        }
      }
    }

    curr_states = next_states;
  }
  
  // find best series of segments
  state_t best = null_state;
  for (int buffer = 0; buffer <= max_buffer; ++buffer) {
    for (int chunk_quality = 0; chunk_quality < int(segments.size()); ++chunk_quality) {
      state_t cand(max_segment, buffer, chunk_quality);
      if (dp.find(cand) != dp.end() && (best == null_state || dp[cand].qoe >= dp[best].qoe)) { 
        best = cand;
      }
    }
  }
 
  if (best == null_state) {
    QUIC_LOG(WARNING) << "[TargetAbr] keeping quality"; 
    return std::make_pair(0, current_quality);
  }

  // find first decision
  std::vector<state_t> states;
  state_t state = best;
  while (state != null_state) {
    states.push_back(state);
    state = dp[state].from;
  }
  std::reverse(states.begin(), states.end());
  state_t first = states.size() > 1 ? states[1] : states[0];
 
  for (auto state : states) {
    QUIC_LOG(WARNING) << state;
  }

  QUIC_LOG(WARNING) << "[TargetAbr] first: " << first << ' ' << dp[first];
  QUIC_LOG(WARNING) << "[TargetAbr] best: " << best << ' ' << dp[best];
  return std::make_pair(dp[best].qoe, first.quality);
}

void TargetAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics);
  StateTracker::registerMetrics(metrics);

  // update future estiamte
  if (interface->BandwidthEstimate() != base::nullopt) {
    if (bw_estimator->empty() || last_bandwidth.value().value != bw_estimator->last()) {
      bw_estimator->sample(last_bandwidth.value().value);
    }
  }

  adjustCC();
} 

int TargetAbr::decideQuality(int index) {
  if (index <= 1 || index > int(segments[0].size())) {
    return 0; 
  }

  int bandwidth = (int)average_bandwidth->value_or(bitrate_array[0]);
  QUIC_LOG(WARNING) << bandwidth << '\n';

  // Get search range for bandwidth target
  int estimator = (int)bw_estimator->value_or(bandwidth);
  if (estimator < 0) {
    // overflow
    estimator = bandwidth;
  }

  QUIC_LOG(WARNING) << estimator << '\n';
  int min_bw = int(fmin(estimator, bandwidth) * (1. - TargetAbrConstants::qoe_delta));
  int max_bw = int(estimator * (1. + TargetAbrConstants::qoe_delta));
  
  // Compute new bandwidth target -- this function should be strictly increasing 
  // as with extra bandwidth we can take the exact same choices as we had before
  bandwidth_target = max_bw;
  int qoe_max_bw = qoe(max_bw).first; 
  int step = TargetAbrConstants::step;
  while (
    bandwidth_target - step >= min_bw && 
    qoe(bandwidth_target - step).first >= TargetAbrConstants::qoe_percentile * qoe_max_bw
  ) {
    //QUIC_LOG(WARNING) << "[TargetAbr]:" << bandwidth_target << ", " << max_bw << "]";
    bandwidth_target -= step;
  }

  QUIC_LOG(WARNING) << "[TargetAbr] bandwidth interval: [" << min_bw << ", " << max_bw << "]";
  QUIC_LOG(WARNING) << "[TargetAbr] bandwidth current: " << bandwidth;
  QUIC_LOG(WARNING) << "[TargetAbr] bandwidth estimator: " << estimator;
  QUIC_LOG(WARNING) << "[TargetAbr] bandwidth target: " << bandwidth_target;

  // Return next quality
  return qoe(TargetAbrConstants::safe_downscale * bandwidth).second;
}

void TargetAbr::adjustCC() {
  // Note we use adjusted level
  if (last_bandwidth == base::nullopt) { 
    return;
  }

  int bandwidth = last_bandwidth.value().value;
  if (bandwidth != last_adjustment_bandwidth) {
    double proportion = 1. * bandwidth / bandwidth_target;
    QUIC_LOG(WARNING) << "[TargetAbr] " << bandwidth << ' ' << proportion << '\n';
    if (proportion >= 1.3) {
      interface->proposePacingGainCycle(std::vector<float>{1, 0.8, 1, 0.8, 1, 1, 1, 1});
    } else if (proportion >= 0.9) {
      interface->proposePacingGainCycle(std::vector<float>{1.25, 0.75, 1, 1, 1, 1, 1, 1});
    } else if (proportion >= 0.5) {
      interface->proposePacingGainCycle(std::vector<float>{1.2, 1, 1.2, 1, 1, 1, 1, 1});
    } else {
      interface->proposePacingGainCycle(std::vector<float>{1.5, 1, 1.5, 1, 1, 1, 1, 1});
    }
    last_adjustment_bandwidth = bandwidth;
  }
}

/**
 * TargetAbr - end 
 **/

/**
 * TargetAbr2 - begin
 **/

TargetAbr2::TargetAbr2(const std::shared_ptr<DashBackendConfig>& config) 
  : SegmentProgressAbr(config) 
  , bw_estimator(new structs::LineFitEstimator<double>(
      TargetAbrConstants::bandwidth_window,
      TargetAbrConstants::time_delta,
      TargetAbrConstants::projection_window
    ))
  , bandwidth_target(bitrate_array[0]) 
  , interface(BbrTarget::BbrInterface::GetInstance()) 
  , last_player_time(abr_schema::Value(0, 0)) 
  , last_buffer_level(abr_schema::Value(0, 0)) 
  , average_bandwidth(new structs::WilderEMA<double>(StateTrackerConstants::bandwidth_window))
  , last_bandwidth(base::nullopt) 
  , last_rtt(base::nullopt) 
  , last_timestamp(0) {} 

TargetAbr2::~TargetAbr2() {}

int TargetAbr2::vmaf(const int quality, const int index) {
  return segments[quality][index].vmaf;
}

double TargetAbr2::localQoe(int current_vmaf, int last_vmaf, int rebuffer, int buffer) {
  return 1. * TargetAbrConstants::alpha * current_vmaf
    - 1. * TargetAbrConstants::beta * fabs(current_vmaf - last_vmaf)
    - 1. * TargetAbrConstants::gamma * rebuffer / ::SECOND;
}

// [TODO] Extract common TargetAbr functions...
std::pair<double, int> TargetAbr2::qoe(const double bandwidth) {
  // compute current_vmaf, start_index, start_buffer
  int last_index = this->decision_index - 1; 
  int current_quality = decisions[last_index].quality;
  int current_vmaf = TargetAbr2::vmaf(current_quality, last_index); 
  int start_index = last_index + 1;
  int start_buffer = last_buffer_level.value;

  // DP
  std::function<size_t (const state_t &)> hash = [](const state_t& state) {
    size_t seed = 0;
    seed ^= std::hash<int>()(state.segment) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    seed ^= std::hash<int>()(state.buffer) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    seed ^= std::hash<int>()(state.quality) + 0x9e3779b9 + (seed << 6) + (seed >> 2);
    return seed;
  };
  std::unordered_map<state_t, value_t, std::function<size_t (const state_t&)> > dp(0, hash);
  std::unordered_set<state_t, std::function<size_t (const state_t&)> > curr_states(0, hash);

  int buffer_unit = 40;
  int max_buffer = 100 * ::SECOND / buffer_unit;
  state_t null_state, start_state(last_index, start_buffer / buffer_unit, current_quality);
  dp[start_state] = value_t(0, current_vmaf, null_state);
  curr_states.insert(start_state);

  int max_segment = 0;
  for (int current_index = last_index; current_index < start_index + TargetAbrConstants::horizon; ++current_index) {
    if (current_index + 2 >= int(segments[0].size())) {
      continue;  
    }

    std::unordered_set<state_t, std::function<size_t (const state_t&)> > next_states(0, hash);
    for (auto &from : curr_states) {
      int max_quality = std::min(int(segments.size()) - 1, from.quality + 1);
      int min_quality = std::max(0, from.quality - 2);
      for (int chunk_quality = min_quality; chunk_quality <= max_quality; ++chunk_quality) {
        double current_buffer = from.buffer * buffer_unit;
        double rebuffer = 0;
        
        double size_kb = 8. * segments[chunk_quality][current_index + 1].size / ::SECOND;
        double download_time_ms = size_kb / bandwidth * ::SECOND;

        // simulate buffer changes
        if (current_buffer < download_time_ms) {
          rebuffer = download_time_ms - current_buffer;
          current_buffer = 0;
        } else {
          current_buffer -= download_time_ms;
        }

        int segment_length_ms = get_segment_length_ms(segments, current_index, chunk_quality);
        current_buffer += segment_length_ms;
        current_buffer = std::min(current_buffer, 1. * max_buffer * buffer_unit);

        // compute next state
        state_t next(current_index + 1, current_buffer / buffer_unit, chunk_quality);

        // compute current and last vmaf
        int current_vmaf = TargetAbr2::vmaf(chunk_quality, current_index + 1);
        int last_vmaf    = dp[from].vmaf;
        
        // compute qoe
        double qoe = dp[from].qoe + localQoe(current_vmaf, last_vmaf, rebuffer, current_buffer);

        if (dp.find(next) == dp.end() || dp[next].qoe < qoe) {
          dp[next] = value_t(qoe, current_vmaf, from); 
          next_states.insert(next);

          max_segment = std::max(max_segment, current_index + 1);
        }
      }
    }

    curr_states = next_states;
  }
  
  // find best series of segments
  state_t best = null_state;
  for (int buffer = 0; buffer <= max_buffer; ++buffer) {
    for (int chunk_quality = 0; chunk_quality < int(segments.size()); ++chunk_quality) {
      state_t cand(max_segment, buffer, chunk_quality);
      if (dp.find(cand) != dp.end() && (best == null_state || dp[cand].qoe >= dp[best].qoe)) { 
        best = cand;
      }
    }
  }
 
  if (best == null_state) {
    QUIC_LOG(WARNING) << "[TargetAbr2] keeping quality"; 
    return std::make_pair(0, current_quality);
  }

  // find first decision
  std::vector<state_t> states;
  state_t state = best;
  while (state != null_state) {
    states.push_back(state);
    state = dp[state].from;
  }
  std::reverse(states.begin(), states.end());
  state_t first = states.size() > 1 ? states[1] : states[0];
 
  QUIC_LOG(WARNING) << "[TargetAbr2] first: " << first << ' ' << dp[first];
  QUIC_LOG(WARNING) << "[TargetAbr2] best: " << best << ' ' << dp[best];
  return std::make_pair(dp[best].qoe, first.quality);
}

void TargetAbr2::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics);

  /// Register front-end metrics
  ///
  for (const auto& segment : metrics.segments) {
    last_timestamp = std::max(last_timestamp, segment->timestamp);
  }

  for (auto const& player_time : metrics.playerTime) {
    if (player_time->timestamp > last_player_time.timestamp) {
      last_player_time = *player_time;
    }
  }
  
  for (auto const& buffer_level : metrics.bufferLevel) {
    if (buffer_level->timestamp > last_buffer_level.timestamp) {
      last_buffer_level = *buffer_level;
    }
  }
 
  // [StateTracker] Update Bandwidth estimate
  // Get the bandwidth estiamte as the maximum delivery rate 
  // encountered from the last metrics registeration: i.e. 100ms
  int best_bw_estimate = 0;
  for (auto &delivery_rate : interface->popDeliveryRates()) {
    best_bw_estimate = std::max(best_bw_estimate, delivery_rate);
  }

  if (best_bw_estimate != 0) {
    // limit the bandwidth estimate downloards
    auto bw_value = std::min(best_bw_estimate, int(bitrate_array.back()));
    
    // register last bandwidth
    last_bandwidth = abr_schema::Value(bw_value, last_timestamp);
    average_bandwidth->sample(bw_value); 
    bw_estimator->sample(bw_value);
  }
 
  // [StateTracker] update rtt estiamte
  auto rtt = interface->RttEstimate();
  if (rtt != base::nullopt) {
    last_rtt = abr_schema::Value(rtt.value(), last_timestamp);
  }

  if (last_bandwidth != base::nullopt) {
    QUIC_LOG(WARNING) << " [last bw] " << last_bandwidth.value().value;
  }
  if (!average_bandwidth->empty()) {
    QUIC_LOG(WARNING) << " [bw avg] " << average_bandwidth->value();
  }

  adjustCC();
} 

int TargetAbr2::decideQuality(int index) {
  if (index <= 1 || index > int(segments[0].size())) {
    return 0; 
  }

  int bandwidth = (int)average_bandwidth->value_or(bitrate_array[0]);
  int estimator = (int)bw_estimator->value_or(bandwidth);
  if (estimator < 0) {
    // overflow
    estimator = bandwidth;
  }

  // Get search range for bandwidth target
  int min_bw = int(fmin(estimator, bandwidth) * (1. - TargetAbrConstants::qoe_delta));
  int max_bw = int(estimator * (1. + TargetAbrConstants::qoe_delta));
  
  // Compute new bandwidth target -- this function should be strictly increasing 
  // as with extra bandwidth we can take the exact same choices as we had before
  bandwidth_target = max_bw;
  int qoe_max_bw = qoe(max_bw).first; 
  int step = TargetAbrConstants::step;
  while (
    bandwidth_target - step >= min_bw && 
    qoe(bandwidth_target - step).first >= .95 * qoe_max_bw
  ) {
    bandwidth_target -= step;
  }

  QUIC_LOG(WARNING) << "[TargetAbr2] bandwidth interval: [" << min_bw << ", " << max_bw << "]";
  QUIC_LOG(WARNING) << "[TargetAbr2] bandwidth current: " << bandwidth;
  QUIC_LOG(WARNING) << "[TargetAbr2] bandwidth estimator: " << estimator;
  QUIC_LOG(WARNING) << "[TargetAbr2] bandwidth target: " << bandwidth_target;

  // Adjust target rate
  interface->setTargetRate(bandwidth_target); 

  // Return next quality
  return qoe(TargetAbrConstants::safe_downscale * bandwidth).second;
}

void TargetAbr2::adjustCC() {
}

/**
 * TargetAbr2 - end 
 **/

TargetAbr3::TargetAbr3(const std::shared_ptr<DashBackendConfig>& config) 
  : TargetAbr2(config) {} 

TargetAbr3::~TargetAbr3() {}

double TargetAbr3::localQoe(int current_vmaf, int last_vmaf, int rebuffer, int buffer) {
  return 1. * TargetAbrConstants::alpha * current_vmaf
    - 1. * TargetAbrConstants::beta * fabs(current_vmaf - last_vmaf)
    - 1. * TargetAbrConstants::gamma * rebuffer / ::SECOND
    - 1. * TargetAbrConstants::zetta * buffer / ::SECOND;
}

}

#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
