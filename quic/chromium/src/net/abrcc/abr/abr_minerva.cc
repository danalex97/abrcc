#include "net/abrcc/abr/abr_minerva.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"

#include <chrono>
#include <cmath>

#include <string>
#include <fstream>
#include <streambuf>

#include "base/json/json_value_converter.h"
#include "base/json/json_reader.h"
#include "base/values.h"

#include "net/abrcc/dash_config.h"


#include <sys/types.h> 
#include <dirent.h>

using namespace std::chrono;

namespace {
  const int SECOND = 1000;
}

namespace quic { 

namespace MinervaConstants {
  const int updateIntervalFactor = 25; 
  const int minRttStart = 10;
  const int maxRttStart = 100;
  const int varianceQueueLength = 4;

  const int initMovingAverageRate = -1;
  const int initUtility = 0;
  const double movingAverageRateProportion = .9;

  const double rebufPenalty = 4.3;
  const double smoothPenalty = 1;
  const int horizon = 5;

  const double beta = 2.5; 
  const double gamma = 100.; 

  const int kbitstep = 10;
  const int kbitmin = 300;
  const int kbitmax = 5000;

  const double downScale = .7;
}

MinervaAbr::MinervaAbr(
    const std::shared_ptr<DashBackendConfig>& config,
    const std::string& minerva_config_path_,
    const bool normalize_)
  : interface(MinervaInterface::GetInstance())
  , timestamp_(high_resolution_clock::now()) 
  , update_interval_(base::nullopt) 
  , started_rate_update(false)
  , should_normalize(normalize_)
  , norm()
  , past_rates()
  , moving_average_rate(MinervaConstants::initMovingAverageRate) 
  , last_index(-1)
  , last_timestamp(0)
  , last_quality(-1) 
  , last_buffer(0, 0) {

  // compute normalization map
  computeNormalizationMap(minerva_config_path_);

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
MinervaAbr::~MinervaAbr() {}

static double get_segment_length_sec(
  const std::vector< std::vector<VideoInfo> >& segments,
  const int current_index,
  const int chunk_quality
) {
  int ref_index = current_index;
  while (ref_index + 1 >= int(segments[chunk_quality].size())) {
    ref_index--;
  }
  int segment_length_ms = int(double(::SECOND) * 
    (segments[chunk_quality][ref_index + 1].start_time 
    - segments[chunk_quality][ref_index].start_time)
  );
  return segment_length_ms / ::SECOND;
}

static std::vector<double> get_scale(const std::vector< std::vector<VideoInfo> >& segments) {
  std::vector<double> pqs;
  for (int rate = MinervaConstants::kbitmin; 
           rate <= MinervaConstants::kbitmax; 
           rate += MinervaConstants::kbitstep) {
    std::vector<double> segment_pqs;
    for (int index = 0; index < int(segments[0].size()); ++index) {
      std::vector<double> rates;
      for (int quality = 0; quality < int(segments.size()); ++quality) {
        double time_s = get_segment_length_sec(segments, index, quality);
        double size_kb = 8. * segments[quality][index].size / 1000.;
        
        rates.push_back(size_kb / time_s);
      }

      double pq = 0;
      double downscaled_rate = MinervaConstants::downScale * rate;
      for (int quality = 0; quality < int(segments.size()); ++quality) {
        if (rates[quality] <= downscaled_rate && (int(rates.size()) == quality + 1 || 
                                                  downscaled_rate <= rates[quality + 1])) {
          pq = segments[quality][index].vmaf;
          break;
        }
      }

      segment_pqs.push_back(pq);
    }

    double video_pq = 0;
    for (auto &pq: segment_pqs) {
      video_pq += pq;  
    }
    video_pq /= int(segment_pqs.size());
  
    pqs.push_back(video_pq);    
  }

  return pqs;
}

void MinervaAbr::computeNormalizationMap(const std::string& conf_path_) {
  DIR *dr;
  struct dirent *en;
  dr = opendir(conf_path_.c_str()); 
  std::vector< std::vector<double> > scales;
  while ((en = readdir(dr)) != NULL) {
    std::string file_name(en->d_name);
    if (file_name.find("json") != std::string::npos) {
      // paths list all configurations
      std::string config_path = conf_path_ + "/" + en->d_name;
      QUIC_LOG(WARNING) << config_path;
    
      // load the configuration json
      std::ifstream stream(config_path);
      std::string data((std::istreambuf_iterator<char>(stream)),
                       std::istreambuf_iterator<char>());
 
      base::Optional<base::Value> value = base::JSONReader::Read(data);
      std::unique_ptr<DashBackendConfig> config = std::unique_ptr<DashBackendConfig>(
        new DashBackendConfig()
      );
      base::JSONValueConverter<DashBackendConfig> converter;
      converter.Convert(*value, config.get()); 
      
      // compute segments
      std::vector<std::vector<VideoInfo> > segments = std::vector< std::vector<VideoInfo> >();
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
      
      // compute bitmap scale      
      std::vector<double> scale = get_scale(segments); 
      scales.push_back(scale);
    }
  }

  // compute norm scale
  for (int i = 0; i < int(scales[0].size()); ++i) {
    double cur = 0;
    for (int j = 0; j < int(scales.size()); ++j) {
      cur += scales[j][i];
    }
    cur /= int(scales.size());
    norm.push_back(cur);
  }

  closedir(dr); 
}

double MinervaAbr::normalize(const double pq) const {
  if (pq < norm[0]) {
    return MinervaConstants::kbitmin;
  }
  for (int index = 0, rate = MinervaConstants::kbitmin; 
           rate < MinervaConstants::kbitmax; 
           index++, rate += MinervaConstants::kbitstep) {
    if (norm[index] <= pq && pq <= norm[index + 1]) {
      double x1 = norm[index];
      double x2 = norm[index + 1];
      double y1 = rate;
      double y2 = rate + MinervaConstants::kbitstep;
      double x = pq; 

      return y1 + (x - x1) / (x2 - x1) * (y2 - y1);
    }
  }
  return MinervaConstants::kbitmax;
}


void MinervaAbr::registerAbort(const int index) {}
void MinervaAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  // Update last buffer
  for (const auto& buffer : metrics.bufferLevel) {
    if (buffer->timestamp > last_buffer.timestamp) {
      last_buffer.value = buffer->value;
      last_buffer.timestamp = buffer->timestamp;
    }
  }
  
  // Register loading segments
  for (const auto& segment : metrics.segments) {
    last_timestamp = std::max(last_timestamp, segment->timestamp);
    if (segment->state == abr_schema::Segment::LOADING) {
      last_segment[segment->index] = *segment;
      if (segment->index > last_index) {
        last_index = segment->index;
        last_quality = segment->quality;
      }
    }
  }
}

abr_schema::Decision MinervaAbr::decide() {
  if (updateIntervalMs() != base::nullopt) {
    if (update_interval_ == base::nullopt) {
      // we are at the first update interval
      update_interval_ = updateIntervalMs();
      timestamp_ = high_resolution_clock::now();
      
      // return noop directly
      return abr_schema::Decision();
    }
    
    auto current_time = high_resolution_clock::now();
    duration<double, std::milli> time_span = current_time - timestamp_;
 
    if (time_span.count() > update_interval_.value() / 2 && !started_rate_update) {
      // we are at the start of moment rate udpdate
      onStartRateUpdate();
      started_rate_update = true;
    }

    if (time_span.count() > update_interval_.value()) {
      // call the weight update function
      onWeightUpdate();
      started_rate_update = false;
    
      // update the update_interval_ based on newer min_rtt estimations
      update_interval_ = updateIntervalMs();
      timestamp_ = high_resolution_clock::now();
    }
  }

  // return noop
  return abr_schema::Decision();
}

// Returns the Minerva update time period as a function min_rtt 
base::Optional<int> MinervaAbr::updateIntervalMs() {
  auto min_rtt = interface->minRtt();
  if (min_rtt == base::nullopt) {
    return base::nullopt;
  }
  if (min_rtt.value() < MinervaConstants::minRttStart) {
    return MinervaConstants::minRttStart * MinervaConstants::updateIntervalFactor; 
  }
  if (min_rtt.value() > MinervaConstants::maxRttStart) {
    return MinervaConstants::maxRttStart * MinervaConstants::updateIntervalFactor; 
  }
  return min_rtt.value() * MinervaConstants::updateIntervalFactor; 
}

void MinervaAbr::onStartRateUpdate() {
  // reset the byte counter for second half of the update interval
  interface->resetAckedBytes();
}

void MinervaAbr::onWeightUpdate() {
  double half_interval = (double)update_interval_.value() / 2 / ::SECOND; // in seconds
  int current_rate = (int)(8. * interface->ackedBytes() / half_interval / ::SECOND); // in kbps
  
  // update past rates for the correct conservative rate estimate
  past_rates.push_back(current_rate);
  if (past_rates.size() > MinervaConstants::varianceQueueLength) {
    past_rates.pop_front();
  }

  // initialize of update hte moving average rate
  if (moving_average_rate == MinervaConstants::initMovingAverageRate) {
    moving_average_rate = conservativeRate();
  } else {
    moving_average_rate = MinervaConstants::movingAverageRateProportion * moving_average_rate 
                        + (1 - MinervaConstants::movingAverageRateProportion) * conservativeRate();
  }

  // compute utility
  double utility = computeUtility();
  if (utility != MinervaConstants::initUtility) {
    double link_weight = 1. * moving_average_rate / utility;

    QUIC_LOG(WARNING) << "[Minerva] Current moving average rate: " << moving_average_rate;
    QUIC_LOG(WARNING) << "[Minerva] Weight updated: " << link_weight;

    interface->setLinkWeight(link_weight);
  }
}

int MinervaAbr::conservativeRate() const {
  if (past_rates.size() < MinervaConstants::varianceQueueLength) {
    return int(.8 * past_rates.back()); 
  }

  double mean = 0;
  for (auto &x : past_rates) {
    mean += x;
  }
  mean /= past_rates.size();

  double variance = 0;
  for (auto &x : past_rates) {
    variance += ((double)x - mean) * ((double)x - mean);
  }
  variance /= past_rates.size();
  double std = std::sqrt(variance);

  return std::max(int(.8 * past_rates.back()), int(past_rates.back() - .5 * std));
}
static std::vector<std::vector<int>> cartesian(int depth, int max) {
  std::vector<std::vector<int> > out; 
  if (depth <= 0) {
    out.push_back(std::vector<int>());
    return out;
  }
  std::vector<std::vector<int> > rest = cartesian(depth - 1, max);
  for (int i = 0; i < max; ++i) {
    for (auto &vec : rest) {
      std::vector<int> now = {i};
      for (auto &x : vec) {
        now.push_back(x);
      }
      out.push_back(now);
    }
  }
  return out;
}

static double get_qoe(
  std::vector<std::vector<VideoInfo> > &segments,
  int index,
  int quality, 
  int last_quality,
  int rebuffer
) {
  double qoe = 0;
  qoe += segments[quality][index].vmaf;
  if (last_quality != -1) {
    qoe -= MinervaConstants::beta * std::abs(segments[quality][index].vmaf - segments[last_quality][index - 1].vmaf);
  }
  qoe -= MinervaConstants::gamma * rebuffer;
  return qoe;
}

static const std::tuple<int, double, double> get_best_rate(
  std::vector<int> bitrates,
  std::vector<std::vector<VideoInfo> > segments, 
  int index,
  int last_quality, 
  double buffer,
  double download_rate
) {
  // max reward
  double start_buffer = buffer;
  double max_reward = 0, best_rate = 0, rebuffer = 0, expected_qoe = 0; 
  for (auto &combo : cartesian(MinervaConstants::horizon, segments.size())) {
    double current_rebuffer = 0;
    double current_buffer = start_buffer;
    double bitrate_sum = 0;
    double smooth_diff = 0;
    double current_expected_qoe = 0;
    int last_quality_ = last_quality;
    int combo_size = 0;
  
    for (int position = 0; position < int(combo.size()); ++position) {
      int chunk_quality = combo[position];
      int current_index = index + position;
    
      if (current_index >= int(segments[0].size())) {
        break;
      }

      double size = 8 * segments[chunk_quality][current_index].size / 1000. / 1000.; // in mb
      double download_time = size / download_rate; // in s

      // simulate future buffer
      if (current_buffer < download_time) {
        current_rebuffer += download_time - current_buffer;
        current_buffer = 0;
      } else {
        current_buffer -= download_time;
      }
      current_buffer += current_index + 1 < int(segments.size()) 
        ?   segments[chunk_quality][current_index + 1].start_time 
          - segments[chunk_quality][current_index].start_time
        :   segments[chunk_quality][current_index].start_time
          - segments[chunk_quality][current_index - 1].start_time;
      
      // liner reward for the buffer
      bitrate_sum += bitrates[chunk_quality];
      smooth_diff += std::abs(bitrates[chunk_quality] - bitrates[last_quality_]);
      
      // update current expected qoe
      current_expected_qoe += get_qoe(
        segments, current_index, chunk_quality, last_quality_, current_rebuffer
      ); 
      
      // update last quality after the expected qoe was updated
      last_quality_ = chunk_quality;
      combo_size++;
    }
    current_expected_qoe /= std::max(combo_size, 1);
    
    // total reward for the combo
    double reward = bitrate_sum / 1000.
      - MinervaConstants::rebufPenalty * current_rebuffer
      - MinervaConstants::smoothPenalty * smooth_diff / 1000.;
    if (reward > max_reward) {
      max_reward   = reward;
      rebuffer     = current_rebuffer;
      best_rate    = combo[0];
      expected_qoe = current_expected_qoe;
    }
  }

  return std::make_tuple(best_rate, rebuffer, expected_qoe);
}

double MinervaAbr::computeUtility() {
  if (last_index <= 1) {
    return MinervaConstants::initUtility;
  }
 
  // setting local variables
  int index = last_index;
  int rate = (int)moving_average_rate;

  // setting phi1 and phi2 constants from Minerva paper
  const double phi1 = 1 / (index + 1);
  const double phi2 = 1.;
 
  // computing past qoe
  int last_segment_quality = last_segment[index].quality;
  int prev_segment_quality = last_segment.find(index - 1) == last_segment.end() 
    ? -1 : last_segment[index - 1].quality;
  double past_qoe = get_qoe(segments, index, last_segment_quality, prev_segment_quality, 0);
  QUIC_LOG(WARNING) << "Past qoe: " << past_qoe;

  // computing current qoe and vh
  auto &[cur_segment_quality, rebuffer, vh] = get_best_rate(
    bitrate_array, segments, index + 1, last_quality, last_buffer.value, rate
  );
  QUIC_LOG(WARNING) << "Vh: " << vh;
  double current_qoe = get_qoe(segments, index + 1, cur_segment_quality, last_segment_quality, rebuffer);
  QUIC_LOG(WARNING) << "Curr qoe: " << current_qoe;

  // compute utility
  double utility = (phi1 * past_qoe + phi2 * current_qoe + vh) / (1. + phi1 + phi2);
  QUIC_LOG(WARNING) << "Utility: " << utility;

  if (should_normalize) {
    utility = normalize(utility);
    QUIC_LOG(WARNING) << "Normalized utility: " << utility;
  }

  return utility;
}

}

#pragma GCC diagnostic pop
