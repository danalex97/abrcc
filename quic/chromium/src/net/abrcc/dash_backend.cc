#include "net/abrcc/dash_backend.h"

#include <utility>
#include <string>
#include <fstream>
#include <streambuf>

#include "base/json/json_value_converter.h"
#include "base/json/json_reader.h"
#include "base/values.h"

#include "net/abrcc/dash_config.h"
#include "net/third_party/quiche/src/quic/core/http/spdy_utils.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_text_utils.h"

const std::string API_PATH = "/request";

using spdy::SpdyHeaderBlock;

namespace quic {

DashBackend::DashBackend()
  : cache(new QuicMemoryCacheBackend())
  , backend_initialized_(false) { }
DashBackend::~DashBackend() {}

void DashBackend::registerResource(
  const std::string& domain, 
  const std::string& resource_path, 
  const std::string& resource
) {
  QUIC_LOG(INFO) << "[register resource] " << domain << " -> " << resource 
                 << " : " << resource_path;

  std::ifstream stream(resource_path);
  std::string data((std::istreambuf_iterator<char>(stream)),
                    std::istreambuf_iterator<char>());
  
  if (data.size() == 0) {
    std::ifstream stream(resource_path, std::ios::binary);
    std::string bin_data((std::istreambuf_iterator<char>(stream)),
                          std::istreambuf_iterator<char>());
    data = bin_data;  
  }

  QUIC_LOG(INFO) << "[data] " << data.size() << '\n';
  
  SpdyHeaderBlock response_headers;
  response_headers[":status"] = QuicTextUtils::Uint64ToString(200);
  response_headers["content-length"] = QuicTextUtils::Uint64ToString(data.size());
   
  cache->AddResponse(domain, resource, std::move(response_headers), data);
}

void DashBackend::registerVideo(
  const std::string& domain, 
  const std::string& resource_path, 
  const std::string& resource,
  const int length 
) {
  registerResource(domain, resource_path + "/Header.m4s", resource + "/Header.m4s");
  for (int i = 1; i <= length; ++i) {
    std::string file = "/" + QuicTextUtils::Uint64ToString(i) + ".m4s";
    registerResource(domain, resource_path + file, resource + file);
  }
}

bool DashBackend::InitializeBackend(const std::string& config_path) {
  QUIC_LOG(INFO) << "Starting DASH backend from config: " << config_path;
  
  // read config file
  std::ifstream stream(config_path);
  std::string data((std::istreambuf_iterator<char>(stream)),
                   std::istreambuf_iterator<char>());
 
  // get config
  base::Optional<base::Value> value = base::JSONReader::Read(data);
  DashBackendConfig config;
  base::JSONValueConverter<DashBackendConfig> converter;
  converter.Convert(*value, &config);

  // paths
  std::string dir_path = config_path.substr(0, config_path.find_last_of("/"));
  std::string base_path = dir_path + config.base_path;
  
  // register video player
  registerResource(config.domain, base_path + config.player_config.index, "/");
  registerResource(
    config.domain, base_path + config.player_config.index, config.player_config.index);
  registerResource(
    config.domain, base_path + config.player_config.manifest, config.player_config.manifest);
  registerResource(
    config.domain, base_path + config.player_config.player, config.player_config.player);

  // register videos
  for (const auto& video_config : config.video_configs) {
    std::string resource = video_config->resource;    
    std::string path = dir_path + video_config->path; 
   
    QUIC_LOG(INFO) << "Caching resource " << resource << " at path " << path;
    
    int video_length = 49;
    registerVideo(config.domain, path, resource, video_length);
  }
  
  backend_initialized_ = true;
  return true;
}

bool DashBackend::IsBackendInitialized() const {
  return backend_initialized_;
}

void DashBackend::FetchResponseFromBackend(
  const SpdyHeaderBlock& request_headers,
  const std::string& string, 
  QuicSimpleServerBackend::RequestHandler* quic_stream
) {
  auto pathWrapper = request_headers.find(":path");
  if (pathWrapper != request_headers.end()) {
    auto path = pathWrapper->second;
    if (path == API_PATH) {
    } else {
      cache->FetchResponseFromBackend(request_headers, string, quic_stream);
    }
  } else {
    cache->FetchResponseFromBackend(request_headers, string, quic_stream);
  }
}

void DashBackend::CloseBackendResponseStream(
  QuicSimpleServerBackend::RequestHandler* quic_server_stream
) {}

}  
