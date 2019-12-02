#ifndef ABRCC_DASH_CONFIG_H_
#define ABRCC_DASH_CONFIG_H_

#include "base/json/json_value_converter.h"

namespace quic {

struct VideoConfig {
  std::string resource;
  std::string path;

  VideoConfig();
  VideoConfig(const VideoConfig&) = delete;
  VideoConfig& operator=(const VideoConfig&) = delete;
  ~VideoConfig();

  static void RegisterJSONConverter(base::JSONValueConverter<VideoConfig>* converter) {
    converter->RegisterStringField("resource", &VideoConfig::resource);
    converter->RegisterStringField("path", &VideoConfig::path);
  }
};

struct DashBackendConfig {
  std::string domain;
  std::vector<std::unique_ptr<VideoConfig>> video_configs;

  DashBackendConfig();
  DashBackendConfig(const DashBackendConfig&) = delete;
  DashBackendConfig& operator=(const DashBackendConfig&) = delete;
  ~DashBackendConfig();

  static void RegisterJSONConverter(
      base::JSONValueConverter<DashBackendConfig>* converter) {
    converter->RegisterStringField("domain", &DashBackendConfig::domain);
    converter->RegisterRepeatedMessage<VideoConfig>("video_paths", &DashBackendConfig::video_configs);
  }
};

}

#endif
