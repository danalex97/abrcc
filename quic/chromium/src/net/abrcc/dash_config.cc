#include "net/abrcc/dash_config.h"

namespace quic {

PlayerConfig::PlayerConfig() {}
PlayerConfig::~PlayerConfig() {}

VideoInfo::VideoInfo() {} 
VideoInfo::VideoInfo(double start_time, double vmaf, int size) 
  : start_time(start_time) 
  , vmaf(vmaf)
  , size(size) {}
VideoInfo::VideoInfo(const VideoInfo& info) 
  : start_time(info.start_time)
  , vmaf(info.vmaf) 
  , size(info.size) {}
VideoInfo::~VideoInfo() {}

VideoConfig::VideoConfig() {} 
VideoConfig::~VideoConfig() {}

DashBackendConfig::DashBackendConfig() {}
DashBackendConfig::~DashBackendConfig() {}

}
