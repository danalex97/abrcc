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
 
DashBackend::DashBackend()
  : store(new StoreService())
  , metrics_service(new MetricsService())
  , push_service(new PushService())
  , backend_initialized_(false) 
{
  std::unique_ptr<AbrInterface> interface(new AbrRandom());
  this->abr = std::move(interface); 
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
  std::shared_ptr<DashBackendConfig> config(new DashBackendConfig());
  base::JSONValueConverter<DashBackendConfig> converter;
  converter.Convert(*value, config.get());

  // paths
  std::string dir_path = config_path.substr(0, config_path.find_last_of("/"));
  std::string base_path = dir_path + config->base_path;
 
  // register stores
  store->MetaFromConfig(base_path, config); 
  store->VideoFromConfig(dir_path, config);

  backend_initialized_ = true;
  return true;
}

bool DashBackend::IsBackendInitialized() const {
  return backend_initialized_;
}

void DashBackend::FetchResponseFromBackend(
  const SpdyHeaderBlock& request_headers,
  const std::string& request_body, 
  QuicSimpleServerBackend::RequestHandler* quic_stream
) {
  auto pathWrapper = request_headers.find(":path");
  if (pathWrapper != request_headers.end()) {
    auto path = pathWrapper->second;
    if (path == API_PATH) {
      // new metrics received
      metrics_service->AddMetrics(request_headers, request_body, quic_stream);
    } else if (path.find(API_PATH) != std::string::npos) {
      // [TODO] do this async
      for (auto& metrics : metrics_service->GetMetrics()) {
        abr->registerMetrics(*metrics);
      }
      abr_schema::Decision decision = abr->decide();
      std::string body = decision.serialize();
    
      SpdyHeaderBlock response_headers;
      response_headers[":status"] = QuicTextUtils::Uint64ToString(200);
      response_headers["content-length"] = QuicTextUtils::Uint64ToString(body.length());
      
      auto* quic_response = new QuicBackendResponse(); 
      quic_response->set_response_type(QuicBackendResponse::REGULAR_RESPONSE);
      quic_response->set_headers(std::move(response_headers));
      quic_response->set_body(body);
      quic_response->set_trailers(SpdyHeaderBlock());
      quic_response->set_stop_sending_code(0);

      auto push_info = std::list<QuicBackendResponse::ServerPushInfo>();
      quic_stream->OnResponseBackendComplete(quic_response, push_info); 
    } else {
      store->FetchResponseFromBackend(request_headers, request_body, quic_stream);
    }
  } else {
    store->FetchResponseFromBackend(request_headers, request_body, quic_stream);
  }
}

void DashBackend::CloseBackendResponseStream(
  QuicSimpleServerBackend::RequestHandler* quic_server_stream
) {}

}  
