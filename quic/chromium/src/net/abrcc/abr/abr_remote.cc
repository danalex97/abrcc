#include "net/abrcc/abr/abr_remote.h"

// interface dependencies 
#include "net/abrcc/dash_config.h"
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

// data struct dependecies
#include "net/abrcc/structs/estimators.h" // LineFitEstimator

#include "net/abrcc/abr/abr_target.h" // TargetAbr2

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


namespace RemoteAbrConstants {
  // horizon for adjustment for bandwidth
  const int horizon_adjustment = 5;
  
  // constants for deciding quality
  const double safe_downscale = .8;
  const double endgame_safe_downscale = .7;
}

namespace quic {

RemoteAbr::RemoteAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : TargetAbr2(config)
  , gap_interface(BbrGap::BbrInterface::GetInstance()) {} 

RemoteAbr::~RemoteAbr() {}

void RemoteAbr::registerMetrics(const abr_schema::Metrics &metrics) {
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
  // [RemoteAbr] we want to use estimates from both interfaces since we don't
  // know which one will be used
  int best_bw_estimate = 0;
  for (auto &delivery_rate : interface->popDeliveryRates()) {
    best_bw_estimate = std::max(best_bw_estimate, delivery_rate);
  }
  for (auto &delivery_rate : gap_interface->popDeliveryRates()) {
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


int RemoteAbr::getTargetDecision(
  int current_bandwidth 
) {
  return 0;
}

int RemoteAbr::decideQuality(int index) {
  if (index <= 1 || index > int(segments[0].size())) {
    return 0; 
  }

  int last_index = this->decision_index - 1; 
  int bandwidth = (int)average_bandwidth->value_or(bitrate_array[0]);
 
  // Compute new bandwidth target -- this function should be strictly increasing 
  // as with extra bandwidth we can take the exact same choices as we had before
  int bandwidth_target = RemoteAbr::getTargetDecision(
    bandwidth
  );

  // Set target
  interface->setTargetRate(std::max(bandwidth, bandwidth_target)); 
  gap_interface->setTargetRate(std::max(bandwidth, bandwidth_target)); 

  // End game
  double safe_downscale = RemoteAbrConstants::safe_downscale;
  if (last_index > int(segments[0].size()) - RemoteAbrConstants::horizon_adjustment) {
    safe_downscale = RemoteAbrConstants::endgame_safe_downscale;
  }
  // Congestion detection
  if (gap_interface->recovery()) {
    safe_downscale = RemoteAbrConstants::endgame_safe_downscale;
  }

  // Return next quality
  return qoe(safe_downscale * bandwidth).second;
}

}

#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
