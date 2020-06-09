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

// HTTP request dependencies 
#include <iostream>
#include <ctype.h>
#include <cstring>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <netinet/in.h>
#include <unistd.h>
#include <sstream>
#include <fstream>
#include <string>
#include <vector>
#include <iterator>
#include <regex>


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

  // ports
  const int remote_port = 5000;
}

namespace quic {

RemoteAbr::RemoteAbr(const std::shared_ptr<DashBackendConfig>& config) 
  : TargetAbr2(config)
  , gap_interface(BbrGap::BbrInterface::GetInstance()) {
  interface->setPacingGainCycle(
    // Use normal pacing gain cycle so that the remote algorithm has full control
    std::vector<float>{1., 1., 1., 1., 1., 1., 1., 1.}
  );
} 

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

template<class T>
static std::string to_string(std::vector<T> v) {
  std::stringstream ss;
  ss << '[';
  for (auto &x : v) {
    ss << x << ',';     
  }
  ss << ']';
  return ss.str();
}


int RemoteAbr::getTargetDecision(
  int avg_bandwidth,
  int current_bandwidth,
  int last_buffer,
  int last_rtt,
  int current_quality,
  int current_index,
  std::vector< std::vector<int> > vmafs,
  std::vector< std::vector<int> > sizes
) {
  int sock;
  struct sockaddr_in client;
  struct hostent *host = gethostbyname("127.0.0.1");

  if (host == NULL || host->h_addr == NULL) {
    QUIC_LOG(WARNING) << "Error retrieving DNS information!";
    return 0;  
  }

  bzero(&client, sizeof(client));
  client.sin_family = AF_INET;
  client.sin_port = htons(RemoteAbrConstants::remote_port);
  memcpy(&client.sin_addr, host->h_addr, host->h_length);

  sock = socket(AF_INET, SOCK_STREAM, 0);
  if (sock < 0) {
      QUIC_LOG(WARNING) << "Error creating socket!";
      return 0;
  }

  if (connect(sock, (struct sockaddr *)&client, sizeof(client)) < 0) {
      close(sock);
      QUIC_LOG(WARNING) << "Could not connect!";
      return 0;
  }

  std::vector<std::string> vmafs_;
  std::vector<std::string> sizes_;
  
  for (auto &x : vmafs) vmafs_.push_back(to_string<int>(x));
  for (auto &x : sizes) sizes_.push_back(to_string<int>(x));

  if (vmafs.size() < RemoteAbrConstants::horizon_adjustment) {
    QUIC_LOG(WARNING) << "Ignore end of video!";
    QUIC_LOG(WARNING) << to_string<std::string>(vmafs_);
    return 0;
  }

  std::stringstream ss;
  ss << "GET /target_bandwidth" << "?"
     << "avg_bandwidth=" << avg_bandwidth
     << "&current_bandwidth=" << current_bandwidth
     << "&last_buffer=" << last_buffer
     << "&last_rtt=" << last_rtt
     << "&current_quality=" << current_quality
     << "&vmafs=" << to_string<std::string>(vmafs_)
     << "&sizes=" << to_string<std::string>(sizes_)
     << "&current_index=" << current_index
     << " HTTP/1.1\r\n"
     << "Host: api.themoviedb.org\r\n"
     << "Accept: application/json\r\n"
     << "\r\n\r\n";
  std::string request = ss.str();
  QUIC_LOG(WARNING) << "Request: " << request;

  if (send(sock, request.c_str(), request.length(), 0) != (int)request.length()) {
      QUIC_LOG(WARNING) << "Error sending request!";
      return 0;
  }

  std::stringstream output;
  char cur;
  while (read(sock, &cur, 1) > 0) {
    output << cur;
  }
  std::vector<std::string> lines(std::istream_iterator<std::string>{output},
                                 std::istream_iterator<std::string>());

  if (std::regex_match(lines.back(), std::regex("[(-|+)|][0-9]+"))) {
    int decision = std::stoi(lines.back());
    QUIC_LOG(WARNING) << "Remote target bandwidth: " << decision; 
    return decision;
  } else { 
    QUIC_LOG(WARNING) << "Remote target bandwidth wrongly formatted!";
    return 0;
  }
}

int RemoteAbr::decideQuality(int index) {
  if (index <= 1 || index > int(segments[0].size())) {
    return 0; 
  }

  int last_index = this->decision_index - 1; 
  int current_quality = decisions[last_index].quality;
  int bandwidth = (int)average_bandwidth->value_or(bitrate_array[0]);
  int curr_bandwidth = bandwidth;
  if (last_bandwidth != base::nullopt) {
    curr_bandwidth = last_bandwidth.value().value;
  }
  int curr_rtt = 0;
  if (last_rtt != base::nullopt) {
    curr_rtt = last_rtt.value().value;
  }
  std::vector< std::vector<int> > vmafs;
  std::vector< std::vector<int> > sizes;
  
  for (int i = last_index; i < last_index + RemoteAbrConstants::horizon_adjustment; ++i) {
    if (i >= int(segments[0].size())) {
      continue;
    }

    std::vector<int> curr_vmaf;
    std::vector<int> curr_size;
    for (int j = 0; j < int(segments.size()); ++j) { 
      curr_vmaf.push_back((int)segments[j][i].vmaf);
      curr_size.push_back(segments[j][i].size);
    }

    vmafs.push_back(curr_vmaf);
    sizes.push_back(curr_size);
  }

  // Compute new bandwidth target -- this function should be strictly increasing 
  // as with extra bandwidth we can take the exact same choices as we had before
  int bandwidth_target = RemoteAbr::getTargetDecision(
    bandwidth,
    curr_bandwidth,
    last_buffer_level.value,   
    curr_rtt,
    current_quality,
    last_index,
    vmafs,
    sizes
  );

  // Set target -- set to target, not max between BW and target
  interface->setTargetRate(bandwidth_target); 
  gap_interface->setTargetRate(bandwidth_target); 

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
