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

// Long-polling service. Contains a cache of hanging QUIC requests with an attached 
// handler. Allow the following operations:
//  -- adding an entry to cache
//  -- sending the response(asynchronous, yet guaranteed, operation)
//  -- accessing a cache entry: returns a unique pointer that allows modifications 
//       to the request
// All methods are protected by a read-write lock.
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

  // Add a handing request, together with a request handler(to be called on sending
  // response) to the polling service cache.
  void AddRequest(
    const spdy::SpdyHeaderBlock& request_headers,
    const std::string& request_body,
    QuicSimpleServerBackend::RequestHandler* quic_server_stream);

  // Send the response to the `request_path` cache entry by overriding the 
  // `response_body` with a new one and calling the associated request handler.
  bool SendResponse(
    const std::string request_path,
    const QuicStringPiece response_body);
  
  // Recover a mutable cache entry.
  std::unique_ptr<PollingService::CacheEntry> GetEntry(
    const std::string request_path);

 private:
  std::unordered_map<std::string, std::unique_ptr<CacheEntry>> stream_cache; 
  mutable QuicMutex mutex_;
};

}

#endif
