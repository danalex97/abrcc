#include "net/abrcc/abr/abr_worthed.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-const-variable"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"

// data structure dependecies: WilderEMA
#include "net/abrcc/structs/averages.h"

namespace {
  const int SECOND = 1000; 
}

namespace quic {

/**
 * State tracker used to compute:
 *  - last player time
 *  - last buffer time
 *  - last bandwidth 
 *  - last rtt
 * 
 *  - Wilder EMA of bandwidth 
 **/

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
  const int segment_size_ms = 5 * ::SECOND;
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


}

#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
