#ifndef ABRCC_SERVICE_STORE_H_
#define ABRCC_SERVICE_STORE_H_

#include "net/abrcc/dash_config.h"

#include "base/threading/thread.h"

#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_memory_cache_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"

namespace quic {

class StoreService {
 public:
  StoreService();
  StoreService(const StoreService&) = delete;
  StoreService& operator=(const StoreService&) = delete;
  ~StoreService();

  void VideoFromConfig(const std::string& dir_path, std::shared_ptr<DashBackendConfig> config);
  void MetaFromConfig(const std::string& base_path, std::shared_ptr<DashBackendConfig> config);
  
  void FetchResponseFromBackend(
    const spdy::SpdyHeaderBlock& request_headers,
    const std::string& string, 
    QuicSimpleServerBackend::RequestHandler* quic_stream
  );

  std::unique_ptr<QuicMemoryCacheBackend> cache;
 private:
  std::shared_ptr<DashBackendConfig> config;
  std::string base_path;
  std::string dir_path;
  
  void registerResource(
    const std::string& domain, 
    const std::string& base_path,
    const std::string& resource);
  void registerVideo(
    const std::string& domain,
    const std::string& base_path,
    const std::string& resource,
    const int video_length);
  std::unique_ptr<base::Thread> registerVideoAsync(
    const std::string& domain,
    const std::string& base_path,
    const std::string& resource,
    const int video_length);
};

}  

#endif  
