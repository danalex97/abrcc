#include "net/abrcc/abr/abr.h"

#include "net/abrcc/dash_config.h"
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include "net/abrcc/structs/averages.h"

#include <algorithm>
#include <iostream>
#include <limits>
#include <fstream>

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-const-variable"

namespace {
 
  // [TODO] use the storage service for this
  std::map<int, std::vector<int>> SEGMENTS = std::map<int, std::vector<int>>{
    {5, std::vector<int>{2354772, 2123065, 2177073, 2160877, 2233056, 1941625, 2157535, 2290172, 2055469, 2169201, 2173522, 2102452, 2209463, 2275376, 2005399, 2152483, 2289689, 2059512, 2220726, 2156729, 2039773, 2176469, 2221506, 2044075, 2186790, 2105231, 2395588, 1972048, 2134614, 2164140, 2113193, 2147852, 2191074, 2286761, 2307787, 2143948, 1919781, 2147467, 2133870, 2146120, 2108491, 2184571, 2121928, 2219102, 2124950, 2246506, 1961140, 2155012, 1433658}},
    {4, std::vector<int>{1728879, 1431809, 1300868, 1520281, 1472558, 1224260, 1388403, 1638769, 1348011, 1429765, 1354548, 1519951, 1422919, 1578343, 1231445, 1471065, 1491626, 1358801, 1537156, 1336050, 1415116, 1468126, 1505760, 1323990, 1383735, 1480464, 1547572, 1141971, 1498470, 1561263, 1341201, 1497683, 1358081, 1587293, 1492672, 1439896, 1139291, 1499009, 1427478, 1402287, 1339500, 1527299, 1343002, 1587250, 1464921, 1483527, 1231456, 1364537, 889412}},
    {3, std::vector<int>{1034108, 957685, 877771, 933276, 996749, 801058, 905515, 1060487, 852833, 913888, 939819, 917428, 946851, 1036454, 821631, 923170, 966699, 885714, 987708, 923755, 891604, 955231, 968026, 874175, 897976, 905935, 1076599, 758197, 972798, 975811, 873429, 954453, 885062, 1035329, 1026056, 943942, 728962, 938587, 908665, 930577, 858450, 1025005, 886255, 973972, 958994, 982064, 830730, 846370, 598850}},
    {2, std::vector<int>{668286, 611087, 571051, 617681, 652874, 520315, 561791, 709534, 584846, 560821, 607410, 594078, 624282, 687371, 526950, 587876, 617242, 581493, 639204, 586839, 601738, 616206, 656471, 536667, 587236, 590335, 696376, 487160, 622896, 641447, 570392, 620283, 584349, 670129, 690253, 598727, 487812, 575591, 605884, 587506, 566904, 641452, 599477, 634861, 630203, 638661, 538612, 550906, 391450}},
    {1, std::vector<int>{450283, 398865, 350812, 382355, 411561, 318564, 352642, 437162, 374758, 362795, 353220, 405134, 386351, 434409, 337059, 366214, 360831, 372963, 405596, 350713, 386472, 399894, 401853, 343800, 359903, 379700, 425781, 277716, 400396, 400508, 358218, 400322, 369834, 412837, 401088, 365161, 321064, 361565, 378327, 390680, 345516, 384505, 372093, 438281, 398987, 393804, 331053, 314107, 255954}},
    {0, std::vector<int>{181801, 155580, 139857, 155432, 163442, 126289, 153295, 173849, 150710, 139105, 141840, 156148, 160746, 179801, 140051, 138313, 143509, 150616, 165384, 140881, 157671, 157812, 163927, 137654, 146754, 153938, 181901, 111155, 153605, 149029, 157421, 157488, 143881, 163444, 179328, 159914, 131610, 124011, 144254, 149991, 147968, 161857, 145210, 172312, 167025, 160064, 137507, 118421, 112270}},
  };

}

const int QUALITIES = 6;
const int SECOND = 1000; 
const std::vector<int> bitrateArray = {300, 750, 1200, 1850, 2850, 4300}; // in Kbps

const int RESERVOIR = 5 * SECOND;
const int CUSHION = 10 * SECOND;
const int SEGMENT_TIME = 3594;

namespace quic {

SegmentProgressAbr::SegmentProgressAbr() : decision_index(1), last_timestamp(0) {}
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

RandomAbr::RandomAbr() : SegmentProgressAbr() {}
RandomAbr::~RandomAbr() {}

int RandomAbr::decideQuality(int index) {
  int random_quality = rand() % QUALITIES;
  if (index == 1) {
    random_quality = 0;
  }
  return random_quality;
}

BBAbr::BBAbr() : SegmentProgressAbr()
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
  int n = bitrateArray.size();
  
  if (index == 1) {
    return 0;
  }
 
  int buffer_level = last_buffer_level.value; 
  if (last_segment[index - 1].state == abr_schema::Segment::PROGRESS) { 
    int start_time = index > 2 ? last_segment[index - 2].timestamp : 0;
    int current_time = last_segment[index - 1].timestamp;

    double proportion = 1.0 * last_segment[index - 1].loaded / last_segment[index - 1].total;
    int download_time = 1.0 * (current_time - start_time) * (1 - proportion) / proportion;
    int bonus = SEGMENT_TIME - download_time; 
  
    buffer_level += bonus;  
  } 
  QUIC_LOG(WARNING) << " [last buffer level] " << buffer_level;

  if (buffer_level <= RESERVOIR) {
    bitrate = bitrateArray[0];
  } else if (buffer_level >= RESERVOIR + CUSHION) {
    bitrate = bitrateArray[n - 1];
  } else {
    bitrate = bitrateArray[0] + 1.0 * (bitrateArray[n - 1] - bitrateArray[0]) 
                                * (buffer_level - RESERVOIR) / CUSHION;
  }

  for (int i = n - 1; i >= 0; --i) {
    quality = i;
    if (bitrate >= bitrateArray[i]) {
      break;
    }
  }
  return quality;
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
  const std::vector<int> bitrate_array = ::bitrateArray;
  std::map<int, std::vector<int> > segment_sizes = SEGMENTS;
  
  const int default_bandwidth = bitrate_array[0];
  const int qualities = QUALITIES;
  const int segment_size_ms = 4 * SECOND;
  const double rebuf_penalty = 4.3;
  const double safe_downscale = 0.75;

  const int horizon = 5;
  const int horizon_stochastic = 4;
  const int segments = 49;

  const int reward_delta_stochastic = 4000;
  const int reward_delta = 5000;

  const int reservoir = 5 * SECOND;
  const int cushion = 10 * SECOND;
  const int safe_to_rtt_probe = 10 * SECOND;

  const int bandwidth_window = 10;
  const int segments_upjump_banned = 2;
}

WorthedAbr::WorthedAbr() : SegmentProgressAbr()
               , ban(0)
               , interface(BbrAdapter::BbrInterface::GetInstance()) 
               , is_rtt_probing(true)
               , last_player_time(abr_schema::Value(0, 0)) 
               , last_buffer_level(abr_schema::Value(0, 0)) 
               , average_bandwidth(new structs::WilderEMA<double>(WorthedAbrConstants::bandwidth_window))
               , last_bandwidth(base::nullopt) 
               , last_rtt(base::nullopt) {} 

WorthedAbr::~WorthedAbr() {}

static double compute_reward(
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

    if (current_index > int(WorthedAbrConstants::segment_sizes[chunk_quality].size())) {
      continue;
    }

    double size_kb = 8. * WorthedAbrConstants::segment_sizes[chunk_quality][current_index] / 1000.;
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
    bitrate_sum += WorthedAbrConstants::bitrate_array[chunk_quality];
    smoothness_diff += abs(WorthedAbrConstants::bitrate_array[chunk_quality] 
                             - WorthedAbrConstants::bitrate_array[last_quality]);
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

static std::pair<double, int> compute_reward_and_quality(
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
  
  int depth = std::min(WorthedAbrConstants::segments - start_index, WorthedAbrConstants::horizon);
  depth = stochastic ? std::min(depth, WorthedAbrConstants::horizon_stochastic) : depth;
  for (auto &next : cartesian(depth, WorthedAbrConstants::qualities, percent)) {
    double reward = compute_reward(next, start_index, bandwidth, start_buffer, current_quality);
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
    int bonus = SEGMENT_TIME - download_time; 

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
    : WorthedAbrConstants::default_bandwidth;
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
  double max_bandwidth_kbps = 2 * WorthedAbrConstants::bitrate_array[WorthedAbrConstants::qualities - 1];
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


static double partial_bw_safe(double bw) {
  double bw_mbit = bw / 1000.;
  double bw_max  = WorthedAbrConstants::bitrate_array.back() / 1000.; 

  if (bw_mbit > bw_max) {
    bw_mbit = bw_max;
  }

  // The base fuunction related to the bandwidth should be strictly
  // decreasing as we want to be less aggresive as we have more bandwidth
  return log(bw_max + 1 - bw_mbit) / 2 / log(bw_max + 1);  
}

static double factor(double bw, double delta) {
  double bw_mbit = bw / 1000.;
  double bw_max  = WorthedAbrConstants::bitrate_array.back() / 1000.; 
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
  
static double aggresivity(double bw, double delta) {
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
    auto bw_value = std::min(bandwidth.value(), WorthedAbrConstants::bitrate_array.back());
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

  // adjust congestion control
  //adjustCC();
 
  if (last_bandwidth != base::nullopt) {
    QUIC_LOG(WARNING) << " [last bw] " << last_bandwidth.value().value;
  }
  if (!average_bandwidth->empty()) {
    QUIC_LOG(WARNING) << " [bw avg] " << average_bandwidth->value();
  }
}


int WorthedAbr::decideQuality(int index) {
  if (index == 1) {
    return 0; 
  }
  
  adjustCC();

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

  int bandwidth = (int)average_bandwidth->value_or(WorthedAbrConstants::default_bandwidth);
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
  const std::vector<int> bitrate_array = ::bitrateArray;
  std::map<int, std::vector<int> > segment_sizes = ::SEGMENTS;
  
  const int reservoir = 5 * ::SECOND;

  std::map<int, std::string> vmaf_video_mapping = {
    { 0, "320x180x30_vmaf_score" }, 
    { 1, "640x360x30_vmaf_score" },
    { 2, "768x432x30_vmaf_score" },    
    { 3, "1024x576x30_vmaf_score" },  
    { 4, "1280x720x30_vmaf_score" },
    { 5, "1280x720x60_vmaf_score" }
  };
}

TargetAbr::TargetAbr(const std::string &video_info_path) 
  : SegmentProgressAbr() 
  , video_info(structs::CsvReader<double>(video_info_path)) {}
TargetAbr::~TargetAbr() {}

int TargetAbr::vmaf(const int quality, const int index) {
  auto& key = TargetAbrConstants::vmaf_video_mapping[quality];
  return static_cast<int>(video_info.get(key, index - 1));
}

void TargetAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  SegmentProgressAbr::registerMetrics(metrics);

  std::cout << vmaf(1, 1) << '\n';
  // [TODO] register metrics
} 

int TargetAbr::decideQuality(int index) {
  // [TODO] implement
  return 0;
}

/**
 * TargetAbr - end 
 **/

AbrInterface* getAbr(const std::string& abr_type, const std::shared_ptr<DashBackendConfig>& config) {
  if (abr_type == "bb") {
    QUIC_LOG(WARNING) << "BB abr selected";
    return new BBAbr();
  } else if (abr_type == "random") {
    QUIC_LOG(WARNING) << "Random abr selected";
    return new RandomAbr();
  } else if (abr_type == "worthed") {
    QUIC_LOG(WARNING) << "Worthed abr selected";
    return new WorthedAbr();
  } else if (abr_type == "target") {
    std::string base_path = config->base_path.substr(1);
    std::string video_info_path = base_path + config->player_config.video_info;

    return new TargetAbr(video_info_path);
  }
  QUIC_LOG(WARNING) << "Defaulting to BB abr";
  return new BBAbr();
}

}

#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
