#include "net/abrcc/abr/abr_minerva.h"

#include <chrono>
#include <cmath>
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
}

MinervaAbr::MinervaAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : interface(MinervaInterface::GetInstance())
  , timestamp_(high_resolution_clock::now()) 
  , update_interval_(base::nullopt) 
  , started_rate_update(false)
  , past_rates()
  , moving_average_rate(MinervaConstants::initMovingAverageRate) 
  , last_index(-1)
  , last_timestamp(0) {

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

void MinervaAbr::registerAbort(const int index) {}
void MinervaAbr::registerMetrics(const abr_schema::Metrics &metrics) {
  // Register loading segments
  for (const auto& segment : metrics.segments) {
    last_timestamp = std::max(last_timestamp, segment->timestamp);
    if (segment->state == abr_schema::Segment::LOADING) {
      last_segment[segment->index] = *segment;
      if (segment->index > last_index) {
        last_index = segment->index;
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


double MinervaAbr::computeUtility() {
  if (last_index == -1) {
    return MinervaConstants::initUtility;
  }
  
  int index = last_index;
  int rate = (int)moving_average_rate;

  std::vector<double> rates; // in kbps
  for (int quality = 0; quality < int(bitrate_array.size()); ++quality) {
    double segment_length = get_segment_length_sec(segments, index, quality);
    int segment_size_bits = 8 * segments[quality][index].size;

    rates.push_back(1. * segment_size_bits / segment_length / ::SECOND);
  }

  for (int quality = 0; quality < int(bitrate_array.size()); ++quality) {
    if (rates[quality] <= rate && (int(rates.size()) == quality + 1 || rate <= rates[quality + 1])) {
      if (int(rates.size()) == quality + 1) {
        return segments[quality][index].vmaf;
      }

      // interpolate the vmaf
      double x1 = rates[quality];
      double x2 = rates[quality + 1];
      double x = rate; 
      double y1 = segments[quality][index].vmaf;
      double y2 = segments[quality + 1][index].vmaf;
    
      return y1 + (x - x1) / (x2 - x1) * (y2 - y1);
    }
  }

  return segments[0][index].vmaf;
}

}

