#include "net/abrcc/dash_backend.h"

#include "net/abrcc/abr/abr.h"
#include "net/abrcc/abr/interface.h"

#include "net/abrcc/service/store_service.h"
#include "net/abrcc/service/metrics_service.h"
#include "net/abrcc/service/push_service.h"

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

  std::unique_ptr<StoreService> meta_store;
 
  std::shared_ptr<StoreService> video_store;
  std::shared_ptr<MetricsService> metrics_service;
  std::shared_ptr<PushService> push_service;
 
  std::unique_ptr<AbrLoop> abr_loop;
  
DashBackend::DashBackend()
  : meta_store(new StoreService())
  , video_store(new StoreService())
  , metrics_service(new MetricsService())
  , push_service(new PushService())
  , backend_initialized_(false) 
{
  std::unique_ptr<AbrInterface> interface(new AbrRandom());
  std::unique_ptr<AbrLoop> abr_loop(new AbrLoop(
    std::move(interface),
    metrics_service,
    video_store,
    push_service
  ));
  this->abr_loop = std::move(abr_loop); 
}
DashBackend::~DashBackend() {}

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
 
  // register stores
  meta_store->MetaFromConfig(base_path, config); 
  video_store->VideoFromConfig(dir_path, config);
  
  // start the ABR loop
  abr_loop->Start();

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
      metrics_service->AddMetrics(request_headers, string, quic_stream);
    } else {
      video_store->FetchResponseFromBackend(request_headers, string, quic_stream);
    }
  } else {
    meta_store->FetchResponseFromBackend(request_headers, string, quic_stream);
  }
}

void DashBackend::CloseBackendResponseStream(
  QuicSimpleServerBackend::RequestHandler* quic_server_stream
) {}

}  
