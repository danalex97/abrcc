#ifndef ABRCC_DASH_BACKEND_H_
#define ABRCC_DASH_BACKEND_H_

#include "net/third_party/quiche/src/quic/platform/api/quic_string_piece.h"
#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_memory_cache_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"

namespace quic {

// Backend for serving DASH a single video from memory. The 
// files are loaded by using a JSON config. Wrapper around 
// QuicMemoryCacheBackend.
class DashBackend : public QuicSimpleServerBackend {
 public:
  DashBackend();
  DashBackend(const DashBackend&) = delete;
  DashBackend& operator=(const DashBackend&) = delete;
  ~DashBackend() override;

  // Implements the functions for interface QuicSimpleServerBackend
  bool InitializeBackend(const std::string& config_path) override;
  bool IsBackendInitialized() const override;
  void FetchResponseFromBackend(
      const spdy::SpdyHeaderBlock& request_headers,
      const std::string& request_body,
      QuicSimpleServerBackend::RequestHandler* quic_server_stream) override;
  void CloseBackendResponseStream(
      QuicSimpleServerBackend::RequestHandler* quic_server_stream) override;

 private:
  void registerResource(
    const std::string& domain, 
    const std::string& base_path,
    const std::string& resource);
  void registerVideo(
    const std::string& domain,
    const std::string& base_path,
    const std::string& resource,
    const int video_length);

  std::unique_ptr<QuicMemoryCacheBackend> cache;
  bool backend_initialized_;
};

}  

#endif  
