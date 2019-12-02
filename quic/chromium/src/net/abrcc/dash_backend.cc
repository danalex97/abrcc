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

using spdy::SpdyHeaderBlock;

namespace quic {

void DashBackend::AddVideo(QuicStringPiece host, QuicStringPiece path) {
  // [TODO]
}

DashBackend::DashBackend() 
  : cache(new QuicMemoryCacheBackend())
  , backend_initialized_(false)  {}
DashBackend::~DashBackend() {}


bool DashBackend::InitializeBackend(const std::string& config_path) {
  QUIC_LOG(INFO) << "Starting DASH backend from config: " << config_path;
  
  // read config file
  std::ifstream stream(config_path);
  std::string data((std::istreambuf_iterator<char>(stream)),
                   std::istreambuf_iterator<char>());

  base::Optional<base::Value> value = base::JSONReader::Read(data);
  DashBackendConfig config;
  base::JSONValueConverter<DashBackendConfig> converter;
  converter.Convert(*value, &config);

  // cache->InitializeBackend(config_path);
  backend_initialized_ = true;
  
  return true;
}

bool DashBackend::IsBackendInitialized() const {
  return backend_initialized_;
}

void DashBackend::FetchResponseFromBackend(
    const SpdyHeaderBlock& request_headers,
    const std::string& string, 
    QuicSimpleServerBackend::RequestHandler* quic_stream) {
  // [TODO]
  cache->FetchResponseFromBackend(request_headers, string, quic_stream);
}

void DashBackend::CloseBackendResponseStream(
    QuicSimpleServerBackend::RequestHandler* quic_server_stream) { }

}  
