#ifndef ABRCC_DASH_CONFIG_H_
#define ABRCC_DASH_CONFIG_H_

#include "base/json/json_value_converter.h"

namespace quic {

struct PlayerConfig {
  std::string index;
  std::string manifest;
  std::string player;

  PlayerConfig();
  PlayerConfig(const PlayerConfig&) = delete;
  PlayerConfig& operator=(const PlayerConfig&) = delete;
  ~PlayerConfig();

  static void RegisterJSONConverter(base::JSONValueConverter<PlayerConfig>* converter) {
    converter->RegisterStringField("index", &PlayerConfig::index);
    converter->RegisterStringField("manifest", &PlayerConfig::manifest);
    converter->RegisterStringField("player", &PlayerConfig::player);
  }
};

struct VideoInfo {
  double start_time;
  double vmaf;
  int size;

  VideoInfo();
  VideoInfo(const VideoInfo&) = delete;
  VideoInfo& operator=(const VideoInfo&) = delete;
  ~VideoInfo();

  static void RegisterJSONConverter(base::JSONValueConverter<VideoInfo>* converter) {
    converter->RegisterDoubleField("start_time", &VideoInfo::start_time);
    converter->RegisterDoubleField("vmaf", &VideoInfo::vmaf);
    converter->RegisterIntField("size", &VideoInfo::size);
  }
};

struct VideoConfig {
  std::string resource;
  std::string path;
  int quality;
  std::vector<std::unique_ptr<VideoInfo>> video_info;

  VideoConfig();
  VideoConfig(const VideoConfig&) = delete;
  VideoConfig& operator=(const VideoConfig&) = delete;
  ~VideoConfig();

  static void RegisterJSONConverter(base::JSONValueConverter<VideoConfig>* converter) {
    converter->RegisterStringField("resource", &VideoConfig::resource);
    converter->RegisterStringField("path", &VideoConfig::path);
    converter->RegisterIntField("quality", &VideoConfig::quality);
    converter->RegisterRepeatedMessage<VideoInfo>("video_info", &VideoConfig::video_info);
  }
};

struct DashBackendConfig {
  std::string domain;
  std::string base_path;
  PlayerConfig player_config;
  std::vector<std::unique_ptr<VideoConfig>> video_configs;
  int segments;

  DashBackendConfig();
  DashBackendConfig(const DashBackendConfig&) = delete;
  DashBackendConfig& operator=(const DashBackendConfig&) = delete;
  ~DashBackendConfig();

  static void RegisterJSONConverter(
      base::JSONValueConverter<DashBackendConfig>* converter) {
    converter->RegisterStringField("domain", &DashBackendConfig::domain);
    converter->RegisterStringField("base_path", &DashBackendConfig::base_path);
    converter->RegisterRepeatedMessage<VideoConfig>("video_paths", &DashBackendConfig::video_configs);
    converter->RegisterNestedField<PlayerConfig>("player", &DashBackendConfig::player_config);
    converter->RegisterIntField("segments", &DashBackendConfig::segments);
  }
};

}

#endif
