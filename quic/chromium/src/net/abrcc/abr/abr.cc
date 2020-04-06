#include "net/abrcc/abr/abr.h"

#include "net/abrcc/dash_config.h"
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include "net/abrcc/structs/averages.h"
#include "net/abrcc/structs/estimators.h"

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


const int SECOND = 1000; 

const int RESERVOIR = 5 * SECOND;
const int CUSHION = 10 * SECOND;

namespace quic {

SegmentProgressAbr::SegmentProgressAbr(const std::shared_ptr<DashBackendConfig>& config) : 
  config(config), decision_index(1), last_timestamp(0) {

  // compute segments
  segments = std::vector< std::vector<VideoInfo> >();
  for (int i = 0; i < int(config->video_configs.size()); ++i) {
    for (auto &video_config : config->video_configs) {
      std::string resource = "/video" + std::to_string(i);
      if (resource == video_config->resource) {
        std::vector<VideoInfo> info;
        for (auto &x : video_config->video_info) {
          info.push_back(VideoInfo(
            x->start_time,
            x->vmaf,
            x->size
          ));  
        }
        segments.push_back(info);
      }
    }
  }

  // compute bitrate array
  bitrate_array = std::vector<int>();
  for (auto &video_config : config->video_configs) {
    bitrate_array.push_back(video_config->quality);
  }
  sort(bitrate_array.begin(), bitrate_array.end());
}
SegmentProgressAbr::~SegmentProgressAbr() {}

static void log_segment(abr_schema::Segment &segment) {
  switch (segment.state) {
    case abr_schema::Segment::PROGRESS:
      QUIC_LOG(WARNING) << "segment " << segment.index 
                        << " [progress] " << 1.0 * segment.loaded / segment.total;
      break;
    case abr_schema::Segment::DOWNLOADED:
      QUIC_LOG(WARNING) << "segment " << segment.index << " [downloaded]";
      break;
    case abr_schema::Segment::LOADING:
      QUIC_LOG(WARNING) << "segment " << segment.index << " [loading]";
      break;
  }
}

void SegmentProgressAbr::update_segment(abr_schema::Segment segment) {
  last_segment[segment.index] = segment;
  
  QUIC_LOG(WARNING) << "[segment update @ " << segment.index << "]";
  log_segment(segment);
}

void SegmentProgressAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  for (const auto& segment : metrics.segments) {
    last_timestamp = std::max(last_timestamp, segment->timestamp);

    switch(segment->state) {
      case abr_schema::Segment::LOADING:
        break;
      case abr_schema::Segment::DOWNLOADED:
        if (last_segment.find(segment->index) == last_segment.end() ||
            last_segment[segment->index].state == abr_schema::Segment::PROGRESS) {
          update_segment(*segment);
        }
        break;
      case abr_schema::Segment::PROGRESS:
        if (last_segment.find(segment->index) == last_segment.end() || (
              last_segment[segment->index].state == abr_schema::Segment::PROGRESS &&
              last_segment[segment->index].timestamp < segment->timestamp)) {
          update_segment(*segment);
        }
        break;  
    }
  }
}

bool SegmentProgressAbr::should_send(int index) {
  if (index == 1) {
    return true;
  }

  if (last_segment.find(index - 1) == last_segment.end()) {
    // no stats from previous segment
    return false;
  }

  auto segment = last_segment[index - 1];
  if (segment.state != abr_schema::Segment::PROGRESS) {
    // segment has already been downloaded or loaded
    return true;
  }
  
  if (1.0 * segment.loaded / segment.total >= 0.8) {
    // segment has been downloaded more than 80%
    return true;
  }

  return false;
}

abr_schema::Decision SegmentProgressAbr::decide() { 
  int to_decide = decision_index;
  if (decisions.find(to_decide) == decisions.end() && should_send(to_decide)) {
    // decisions should be idempotent
    decisions[to_decide] = abr_schema::Decision(
      to_decide, 
      decideQuality(to_decide), 
      last_timestamp
    );
    decision_index += 1;

    QUIC_LOG(WARNING) << "[SegmentProgressAbr] new decision: [index] " << decisions[to_decide].index
                      << " [quality] " << decisions[to_decide].quality;
    return decisions[to_decide];
  } else {
    return decisions[to_decide - 1];
  }
}

RandomAbr::RandomAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : SegmentProgressAbr(config) {}
RandomAbr::~RandomAbr() {}

int RandomAbr::decideQuality(int index) {
  int random_quality = rand() % segments.size();
  if (index == 1) {
    random_quality = 0;
  }
  return random_quality;
}

BBAbr::BBAbr(const std::shared_ptr<DashBackendConfig>& config) 
               : SegmentProgressAbr(config)
               , last_player_time(abr_schema::Value(0, 0)) 
               , last_buffer_level(abr_schema::Value(0, 0)) {} 
BBAbr::~BBAbr() {}

void BBAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics);
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
}

int BBAbr::decideQuality(int index) {
  double bitrate = 0;
  int quality = 0;
  int n = bitrate_array.size();
  
  if (index == 1) {
    return 0;
  }
 
  int buffer_level = last_buffer_level.value; 
  if (last_segment[index - 1].state == abr_schema::Segment::PROGRESS) { 
    int start_time = index > 2 ? last_segment[index - 2].timestamp : 0;
    int current_time = last_segment[index - 1].timestamp;

    double proportion = 1.0 * last_segment[index - 1].loaded / last_segment[index - 1].total;
    int download_time = 1.0 * (current_time - start_time) * (1 - proportion) / proportion;
    
    if (index < int(segments[0].size())) {
      last_segment_time_length = int(SECOND * (segments[0][index + 1].start_time - segments[0][index].start_time));
    }
    int bonus = last_segment_time_length - download_time; 
  
    buffer_level += bonus;  
  } 
  QUIC_LOG(WARNING) << " [last buffer level] " << buffer_level;

  if (buffer_level <= RESERVOIR) {
    bitrate = bitrate_array[0];
  } else if (buffer_level >= RESERVOIR + CUSHION) {
    bitrate = bitrate_array[n - 1];
  } else {
    bitrate = bitrate_array[0] + 1.0 * (bitrate_array[n - 1] - bitrate_array[0]) 
                                * (buffer_level - RESERVOIR) / CUSHION;
  }

  for (int i = n - 1; i >= 0; --i) {
    quality = i;
    if (bitrate >= bitrate_array[i]) {
      break;
    }
  }
  return quality;
}

/**
 * State tracker used to compute:
 *  - last player time
 *  - last buffer time
 *  - last bandwidth 
 *  - last rtt
 * 
 *  - Wilder EMA of bandwidth 
 **/

namespace StateTrackerConstants { 
  const int bandwidth_window = 10;
}

StateTracker::StateTracker(std::vector<int> bitrate_array) 
 : interface(BbrAdapter::BbrInterface::GetInstance()) 
 , last_player_time(abr_schema::Value(0, 0)) 
 , last_buffer_level(abr_schema::Value(0, 0)) 
 , average_bandwidth(new structs::WilderEMA<double>(StateTrackerConstants::bandwidth_window))
 , last_bandwidth(base::nullopt) 
 , last_rtt(base::nullopt) 
 , last_timestamp(0)
 , _bitrate_array(bitrate_array) {}

StateTracker::~StateTracker() {}

void StateTracker::registerMetrics(const abr_schema::Metrics &metrics) {
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

  // update bandwidth estiamte
  auto bandwidth = interface->BandwidthEstimate();
  if (bandwidth != base::nullopt) {
    // limit the bandwidth estimate downloards
    auto bw_value = std::min(bandwidth.value(), _bitrate_array.back());
    auto current_gain = interface->PacingGain();
    if (current_gain != base::nullopt && current_gain.value() > 1) {
      // scale down(or up) bw value based on current gain
      // we need this since the current gain is positive during aggresive cycles 
      bw_value = (1.0 / current_gain.value()) * bw_value;
    }
    
    last_bandwidth = abr_schema::Value(bw_value, last_timestamp);
    if (average_bandwidth->empty() 
        || bw_value != average_bandwidth->last()) {
       // [TODO] what happens is the bandwidth is large constantly: i.e. bitrate_array.back()
      
      if (!average_bandwidth->empty() && bw_value <= average_bandwidth->value() * 0.7) {
        // if the BW dropped fast, we drop the average as well
        // note this takes into accout the scaling down of the pacing cycle
        average_bandwidth->sample(bw_value);
      }
      average_bandwidth->sample(bw_value);
    }
  }

  // update rtt estiamte
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
}

/**
 * (1) Worthed ABR
 *   ABR receives:
 *     - bandwidth and rtt estimates from CC. 
 *     - state from front-end
 *   ABR decides:
 *     - safe rate
 *     - worthed rate
 *   Based on QoE estimation of difference between safe and worthed rate, 
 *   we set pacing cycle of BBR Adapter.
 **/

namespace WorthedAbrConstants { 
  const int segment_size_ms = 4 * ::SECOND;
  const double rebuf_penalty = 4.3;
  const double safe_downscale = 0.75;

  const int horizon = 5;
  const int horizon_stochastic = 4;

  const int reward_delta_stochastic = 4000;
  const int reward_delta = 5000;

  const int reservoir = 5 * ::SECOND;
  const int cushion = 10 * ::SECOND;
  const int safe_to_rtt_probe = 10 * ::SECOND;

  const int segments_upjump_banned = 2;
}

WorthedAbr::WorthedAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : SegmentProgressAbr(config)
  , StateTracker(bitrate_array)
  , ban(0)
  , is_rtt_probing(true) {} 

WorthedAbr::~WorthedAbr() {}

double WorthedAbr::compute_reward(
  std::vector<int> qualities, 
  int start_index, 
  int bandwidth,
  int start_buffer,
  int current_quality
) {
  // buffer state
  int current_rebuffer = 0;  
  int current_buffer = start_buffer;
  int last_quality = current_quality;

  // accumators
  double bitrate_sum = 0;
  double smoothness_diff = 0;

  for (size_t i = 0; i < qualities.size(); ++i) {
    int chunk_quality = qualities[i];
    int current_index = start_index + i;

    if (current_index > int(segments[chunk_quality].size())) {
      continue;
    }

    double size_kb = 8. * segments[chunk_quality][current_index].size / 1000.;
    double download_time_ms = size_kb / bandwidth * 1000;

    // simulate buffer changes
    if (current_buffer < download_time_ms) {
      current_rebuffer += download_time_ms - current_buffer;
      current_buffer = 0;
    } else {
      current_buffer -= download_time_ms;
    }
    current_buffer += WorthedAbrConstants::segment_size_ms;
    
    // compute the reward
    bitrate_sum += bitrate_array[chunk_quality];
    smoothness_diff += abs(bitrate_array[chunk_quality] - bitrate_array[last_quality]);
    last_quality = chunk_quality;
  }
  
  // compute reward
  return ( bitrate_sum
         - WorthedAbrConstants::rebuf_penalty * current_rebuffer
         - smoothness_diff);
}

static double rand_prob() {
  return (double)rand() / (RAND_MAX + 1.0);
}

static std::vector<std::vector<int>> cartesian(int depth, int max, double percent) {
  std::vector<std::vector<int> > out; 
  if (depth <= 0) {
    out.push_back(std::vector<int>());
    return out;
  }
  std::vector<std::vector<int> > rest = cartesian(depth - 1, max, 1);
  for (int i = 0; i < max; ++i) {
    for (auto &vec : rest) {
      if (rand_prob() > percent) {
        continue;
      }
      std::vector<int> now = {i};
      for (auto &x : vec) {
        now.push_back(x);
      }
      out.push_back(now);
    }
  }
  return out;
}

std::pair<double, int> WorthedAbr::compute_reward_and_quality(
  int start_index, 
  int bandwidth,
  int start_buffer,
  int current_quality,
  bool stochastic,
  int last_decision
) {
  double best = -std::numeric_limits<double>::infinity();
  double percent = stochastic ? .2 : 1;
  int quality = 0;
  
  int depth = std::min(int(segments[quality].size()) - start_index, WorthedAbrConstants::horizon);
  depth = stochastic ? std::min(depth, WorthedAbrConstants::horizon_stochastic) : depth;
  for (auto &next : cartesian(depth, segments.size(), percent)) {
    double reward = compute_reward(
      next, start_index, bandwidth, start_buffer, current_quality
    );
    if (reward > best) {
      best = reward;
      if (!next.empty()) {
        quality = next[0];
      } else {
        // [TODO] this is not great for the last segment
        // we should do something different here, maybe...
        quality = last_decision;
      }
    }
  }
  return std::make_pair(best, quality);
}


int WorthedAbr::adjustedBufferLevel(int index) {
  int buffer_level = last_buffer_level.value; 
  if (last_segment[index - 1].state == abr_schema::Segment::PROGRESS) { 
    int start_time = index > 2 ? last_segment[index - 2].timestamp : 0;
    int current_time = last_segment[index - 1].timestamp;

    double proportion = 1.0 * last_segment[index - 1].loaded / last_segment[index - 1].total;
    int download_time = 1.0 * (current_time - start_time) * (1 - proportion) / proportion;
    if (index < int(segments[0].size())) {
      last_segment_time_length = int(SECOND * (segments[0][index + 1].start_time - segments[0][index].start_time));
    }
    int bonus = last_segment_time_length - download_time; 

    buffer_level += bonus;  
  } 
  return buffer_level;
}


// Compute rate_safe and rate_worthed
std::pair<int, int> WorthedAbr::computeRates(bool stochastic) {
  // State:
  //  - horizon  | static
  //  - buffer
  //  - bandwidth
  //  - lastest decision
  int bandwidth_kbps = last_bandwidth != base::nullopt 
    ? last_bandwidth.value().value
    : bitrate_array[0];
  int last_index = this->decision_index - 1; 
  int last_quality = this->decisions[last_index].quality;
  // int buffer_level = adjustedBufferLevel(last_index);
  // Be pesimistic here
  int buffer_level = last_buffer_level.value;

  // compute rate_safe
  double rate_safe = bandwidth_kbps * WorthedAbrConstants::safe_downscale;
  double reward_safe = compute_reward_and_quality(
    last_index + 1,
    rate_safe,
    buffer_level,
    last_quality,
    stochastic,
    decisions[last_index].quality
  ).first; 
  QUIC_LOG(INFO) << "[WorthedAbr] rate safe: " << rate_safe;
 
  // compute rate worthed
  double scale_step_kbps = stochastic ? 150 : 100;
  double needed_reward = stochastic ? WorthedAbrConstants::reward_delta_stochastic 
                                 : WorthedAbrConstants::reward_delta;

  double current_bandwidth_kbps = bandwidth_kbps * WorthedAbrConstants::safe_downscale;
  double max_bandwidth_kbps = 2 * bitrate_array.back();
  double reward = reward_safe;
  while (current_bandwidth_kbps <= max_bandwidth_kbps) {
    current_bandwidth_kbps += scale_step_kbps;
    reward = compute_reward_and_quality(
      last_index + 1,
      current_bandwidth_kbps,
      buffer_level,
      last_quality,
      stochastic,
      decisions[last_index].quality
    ).first;
    if (reward - reward_safe >= needed_reward) {
      break;
    }
  }
  double rate_worthed = current_bandwidth_kbps; 
  QUIC_LOG(INFO) << "[WorthedAbr] rate worthed: " << rate_worthed;

  return std::make_pair(rate_safe, rate_worthed);
}

double WorthedAbr::partial_bw_safe(double bw) {
  double bw_mbit = bw / 1000.;
  double bw_max  = bitrate_array.back() / 1000.; 

  if (bw_mbit > bw_max) {
    bw_mbit = bw_max;
  }

  // The base fuunction related to the bandwidth should be strictly
  // decreasing as we want to be less aggresive as we have more bandwidth
  return log(bw_max + 1 - bw_mbit) / 2 / log(bw_max + 1);  
}

double WorthedAbr::factor(double bw, double delta) {
  double bw_mbit = bw / 1000.;
  double bw_max  = bitrate_array.back() / 1000.; 
  double delta_mbit = delta / 1000.;

  if (bw_mbit > bw_max) {
    bw_mbit = bw_max;
  }
  
  // The factor function should be increasing over delta as the difference is small
  // and decreasing as the bandwidth increases.
  double base_factor = std::pow(std::log(bw_max + 1. - bw_mbit), 2.) 
    / (bw_max * 0.8) / std::pow(bw_mbit, (2. / bw_max));
  double factor = 1. - (1. - base_factor) * ((delta_mbit + 1.) / (bw_max + 1.)); 

  return factor;
}
  
double WorthedAbr::aggresivity(double bw, double delta) {
  double aggr_factor = factor(bw, delta);
  double value = partial_bw_safe(bw);

  QUIC_LOG(INFO) << "[WorthedAbr] partial values: " << value << ' ' << aggr_factor << '\n';
  return std::max(std::min(value * aggr_factor, 1.), 0.);
}

void WorthedAbr::setRttProbing(bool probe) {
  if (is_rtt_probing != probe) {
    is_rtt_probing = probe;
    interface->setRttProbing(probe);
  }
  // [TODO] maybe be less aggressive after RTT probing?
}

void WorthedAbr::adjustCC() {
  if (decision_index <= 1) {
    // Adjust CC only after a few segments
    return;
  }
 
  // Note here we use the adjusted level
  const auto& buffer_level = adjustedBufferLevel(decision_index - 1);
  const auto& [bw_safe, bw_worthed] = computeRates(true);   

  // for RTT probing we need to have enough pieces downloaded
  if (buffer_level <= WorthedAbrConstants::safe_to_rtt_probe && decision_index > 3) {
    setRttProbing(false);
  } else {
    setRttProbing(true);
  }
  
  double aggress = 0;
  if (buffer_level <= WorthedAbrConstants::reservoir) {
    aggress = 1;
  } else if (buffer_level >= WorthedAbrConstants::reservoir + WorthedAbrConstants::cushion) {
    aggress = 0;
  } else {
    aggress = aggresivity(bw_safe, bw_worthed - bw_safe);
  }
  
  QUIC_LOG(WARNING) << "[WorthedAbr] aggressivity: " << aggress;
  if (aggress == 1) {
    interface->proposePacingGainCycle(std::vector<float>{1.5, 1, 1.5, 1, 1, 1, 1, 1});
  } else if (aggress >= 0.4) {
    interface->proposePacingGainCycle(std::vector<float>{1.3, 0.8, 1.3, 0.8, 0.8, 1, 1, 1});
  } else { 
    interface->proposePacingGainCycle(std::vector<float>{1.25, 0.75, 1, 1, 1, 1, 1, 1});
  }
}

void WorthedAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics);
  StateTracker::registerMetrics(metrics);

  adjustCC();
}


int WorthedAbr::decideQuality(int index) {
  if (index <= 2 || index > int(segments[0].size())) {
    return 0; 
  }
  
  // get constants
  int last_index = this->decision_index - 1; 
  int last_quality = this->decisions[last_index].quality;
  // We use the current buffer level, so we are less optimistic
  int buffer_level = last_buffer_level.value;

  // Be even less optimistic -- This way we can try to always have 
  // bigger buffers
  buffer_level -= WorthedAbrConstants::reservoir;
  if (buffer_level < 0) {
    buffer_level = 0;
  }

  int bandwidth = (int)average_bandwidth->value_or(bitrate_array[0]);
  int quality = compute_reward_and_quality(
    last_index + 1,
    bandwidth * WorthedAbrConstants::safe_downscale, 
    buffer_level,
    last_quality,
    false,
    decisions[last_index].quality
  ).second;

  ban -= int(quality >= last_quality);

  // limit jumping up
  if (quality > last_quality) {
    if (ban <= 0) {
      quality = last_quality + 1;
    } else {
      quality = last_quality;
    }
 }

  // [TODO] reduce jumps properly: e.g. dynamic programming
  if (quality < last_quality) {
    ban = WorthedAbrConstants::segments_upjump_banned;
  }
  
  QUIC_LOG(WARNING) << "[WorthedAbr] quality: bandwidth used " << bandwidth;
  QUIC_LOG(WARNING) << "[WorthedAbr] quality: buffer level used " << buffer_level;
  QUIC_LOG(WARNING) << "[WorthedAbr] quality " << quality;
  
  return quality;
}


/**
 * WortherAbr -- end
 **/


/**
 * TargetAbr - begin
 **/

namespace TargetAbrConstants { 
  const int reservoir = 5 * ::SECOND;
  const int horizon = 10;  

  // constants used for QoE function weights
  const double alpha = 1.;
  const double beta = 2.5; 
  const double gamma = 25.; 

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

    int qoe;
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
  int max_buffer = 40 * ::SECOND / buffer_unit;
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
      // QUIC_LOG(WARNING) << from;
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
        current_buffer += WorthedAbrConstants::segment_size_ms;
        current_buffer = std::min(current_buffer, 1. * max_buffer * buffer_unit);

        // compute next state
        state_t next(current_index + 1, current_buffer / buffer_unit, chunk_quality);

        // compute current and last vmaf
        int current_vmaf = TargetAbr::vmaf(chunk_quality, current_index + 1);
        int last_vmaf    = dp[from].vmaf;
        
        // compute qoe
        double qoe = dp[from].qoe;
        qoe += 1. * TargetAbrConstants::alpha * current_vmaf;
        qoe -= 1. * TargetAbrConstants::beta * fabs(current_vmaf - last_vmaf);
        qoe -= 1. * TargetAbrConstants::gamma * rebuffer / ::SECOND;

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
  int max_buffer = 40 * ::SECOND / buffer_unit;
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
        current_buffer += WorthedAbrConstants::segment_size_ms;
        current_buffer = std::min(current_buffer, 1. * max_buffer * buffer_unit);

        // compute next state
        state_t next(current_index + 1, current_buffer / buffer_unit, chunk_quality);

        // compute current and last vmaf
        int current_vmaf = TargetAbr2::vmaf(chunk_quality, current_index + 1);
        int last_vmaf    = dp[from].vmaf;
        
        // compute qoe
        double qoe = dp[from].qoe;
        qoe += 1. * TargetAbrConstants::alpha * current_vmaf;
        qoe -= 1. * TargetAbrConstants::beta * fabs(current_vmaf - last_vmaf);
        qoe -= 1. * TargetAbrConstants::gamma * rebuffer / ::SECOND;

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
 
  // QUIC_LOG(WARNING) << "[TargetAbr2] first: " << first << ' ' << dp[first];
  // QUIC_LOG(WARNING) << "[TargetAbr2] best: " << best << ' ' << dp[best];
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


AbrInterface* getAbr(
  const std::string& abr_type, 
  const std::shared_ptr<DashBackendConfig>& config
) {
  if (abr_type == "bb") {
    QUIC_LOG(WARNING) << "BB abr selected";
    return new BBAbr(config);
  } else if (abr_type == "random") {
    QUIC_LOG(WARNING) << "Random abr selected";
    return new RandomAbr(config);
  } else if (abr_type == "worthed") {
    QUIC_LOG(WARNING) << "Worthed abr selected";
    return new WorthedAbr(config);
  } else if (abr_type == "target") {
    QUIC_LOG(WARNING) << "Target abr selected";
    return new TargetAbr(config);
  } else if (abr_type == "target2") {
    QUIC_LOG(WARNING) << "Target2 abr selected";
    return new TargetAbr2(config);
  }
  QUIC_LOG(WARNING) << "Defaulting to BB abr";
  return new BBAbr(config);
}

}

#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
