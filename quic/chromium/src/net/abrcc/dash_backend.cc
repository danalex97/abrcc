#include "net/abrcc/dash_backend.h"

#include <utility>

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

bool DashBackend::InitializeBackend(const std::string& backend_url) {
  // [TODO]
  QUIC_LOG(INFO) << "Starting DASH backend: " << backend_url;
  
  cache->InitializeBackend(backend_url);
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
