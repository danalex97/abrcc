#ifndef ABRCC_PUSH_SERVICE_H_
#define ABRCC_PUSH_SERVICE_H_

#include <string>
#include <unordered_map>

#include "net/third_party/quiche/src/quic/platform/api/quic_mutex.h"
#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"
#include "net/third_party/quiche/src/quic/core/http/spdy_utils.h"

namespace quic {

// !THREAD_SAFE
class PollingService {
 public:
  class CacheEntry {
    public:
      CacheEntry(
        const spdy::SpdyHeaderBlock& request_headers,
        const std::string request_body,
        QuicSimpleServerBackend::RequestHandler* handler
      );
      CacheEntry(const CacheEntry&) = delete;
      CacheEntry& operator=(const CacheEntry&) = delete;
      ~CacheEntry();

      std::unique_ptr<spdy::SpdyHeaderBlock> base_request_headers;
      std::string request_body;
      QuicSimpleServerBackend::RequestHandler* handler;
  };

  PollingService();
  PollingService(const PollingService&) = delete;
  PollingService& operator=(const PollingService&) = delete;
  ~PollingService();

  void AddRequest(
    const spdy::SpdyHeaderBlock& request_headers,
    const std::string& request_body,
    QuicSimpleServerBackend::RequestHandler* quic_server_stream);

  bool SendResponse(
    const std::string request_path,
    const QuicStringPiece response_body);
   
 private:
  std::unordered_map<std::string, std::unique_ptr<CacheEntry>> stream_cache; 
  mutable QuicMutex mutex_;
};

}

#endif
