#include "net/abrcc/abr/abr_gap.h"

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


namespace GapAbrConstants {
  // horizon for adjustment for bandwidth
  const int horizon_adjustment = 5;
  
  // constants for optimization objective
  const double qoe_percentile = .95;
  const double qoe_delta = .25;
  const int step = 100;

  const double over_percent = 1.25;

  // constants for deciding quality
  const double safe_downscale = .8;
}

namespace {
  const int SECOND = 1000; 
}

namespace quic {

GapAbr::GapAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : TargetAbr2(config) {}

GapAbr::~GapAbr() {}


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


int GapAbr::decideQuality(int index) {
  if (index <= 1 || index > int(segments[0].size())) {
    return 0; 
  }

  int bandwidth = (int)average_bandwidth->value_or(bitrate_array[0]);
  
  // Get search range for bandwidth target
  int min_bw = int(bandwidth * (1. - GapAbrConstants::qoe_delta));
  int max_bw = int(bandwidth * (1. + GapAbrConstants::qoe_delta));

  int last_index = this->decision_index - 1; 
  int current_quality = decisions[last_index].quality;
  int start_buffer = last_buffer_level.value;

  // if we are not looking at biggest quality
  double final_qoe_percentile = GapAbrConstants::qoe_percentile;
  if (current_quality < int(segments.size()) - 1 && 
      last_index < int(segments[0].size()) - GapAbrConstants::horizon_adjustment) {
    // find the index for the smallest index difference
    int index_lowest_difference = last_index + 1;
    int current_difference = 
      segments[current_quality + 1][last_index + 1].vmaf - 
      segments[current_quality][last_index + 1].vmaf; 
    for (int i = last_index + 2; i <= last_index + GapAbrConstants::horizon_adjustment; ++i) {
      int vmaf_diff = segments[current_quality + 1][i].vmaf - segments[current_quality][i].vmaf;
      if (vmaf_diff < current_difference) {
        current_difference = vmaf_diff;
        index_lowest_difference = i;
      }
    }

    // find the average segment size for the next horizion pieces after the planned transition
    int total_size = 0;
    int total_length = 0;
    for (int i = index_lowest_difference; 
             i < index_lowest_difference + GapAbrConstants::horizon_adjustment && 
             i < int(segments[0].size()); ++i) {
      total_size += segments[current_quality + 1][i].size; 
      total_length += get_segment_length_ms(segments, i, current_quality + 1);
    }
    int avg_needed_bw = 8 * total_size / total_length;
  
    int max_bw_suggestion = avg_needed_bw * GapAbrConstants::over_percent; 
    float gain = 1. * (max_bw_suggestion * GapAbrConstants::safe_downscale - min_bw) / min_bw;
  
    // If it looks worthed to be more aggressive and the gain in bandwidth is attainable
    if (max_bw_suggestion > std::max(min_bw, max_bw)) {
      max_bw = std::min(max_bw_suggestion, max_bw * 2);

      // adjust percentile w.r.t. gain
      if (gain < .7) {
        final_qoe_percentile = .99;
      } else if (gain < 1.25) {
        final_qoe_percentile = .95;
      } else {
        final_qoe_percentile = .9;
      }

      // adjust percentile w.r.t. buffer, that is if the buffer is big, then we might
      // try to be more aggressive since we have not much to lose
      if (start_buffer > 15 * ::SECOND) {
        if (final_qoe_percentile == .95) {
          final_qoe_percentile = .99;
        } else if (final_qoe_percentile == .9) {
          final_qoe_percentile = .95;
        }
      }
  

      QUIC_LOG(WARNING) << "[GapAbr] gain: "  << gain;
      QUIC_LOG(WARNING) << "[GapAbr] percentile: "  << final_qoe_percentile;
    }
  }

  // Compute new bandwidth target -- this function should be strictly increasing 
  // as with extra bandwidth we can take the exact same choices as we had before
  bandwidth_target = max_bw;
  int qoe_max_bw = qoe(max_bw).first; 
  int step = GapAbrConstants::step;
  while (
    bandwidth_target - step >= min_bw && 
    qoe(bandwidth_target - step).first >= final_qoe_percentile * qoe_max_bw
  ) {
    bandwidth_target -= step;
  }

  QUIC_LOG(WARNING) << "[GapAbr] bandwidth interval: [" << min_bw << ", " << max_bw << "]";
  QUIC_LOG(WARNING) << "[GapAbr] bandwidth current: " << bandwidth;
  QUIC_LOG(WARNING) << "[GapAbr] bandwidth target: " << bandwidth_target;

  // Adjust target rate -- if the bandwidth estimate decreases, don't force further decrease,
  // that is, use std::max(bandwidth, bandwidth_target)
  interface->setTargetRate(std::max(bandwidth, bandwidth_target)); 

  // Return next quality
  return qoe(GapAbrConstants::safe_downscale * bandwidth).second;
}

}

#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
#pragma GCC diagnostic pop
