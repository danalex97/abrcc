#ifndef ABRCC_PUSH_SERVICE_H_
#define ABRCC_PUSH_SERVICE_H_

#include <string>
#include <unordered_map>

#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"
#include "net/third_party/quiche/src/quic/core/http/spdy_utils.h"

namespace quic {

// !THREAD_USAFE
class PushService {
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

  PushService();
  PushService(const PushService&) = delete;
  PushService& operator=(const PushService&) = delete;
  ~PushService();

  // Register a path on which PUSHED will be sent from the backend.
  //
  // Note the RequestHandler is a raw pointer, so we want to ensure the
  // object is not deleted when using this service.
  void RegisterPath(
    const spdy::SpdyHeaderBlock& request_headers,
    const std::string& request_body,
    QuicSimpleServerBackend::RequestHandler* quic_server_stream);

  // Push a response towards a path.
  //
  // The response has to contain the host, path, response headers and 
  // the response body.
  bool PushResponse(
    const std::string request_path,
    const std::string host,
    const std::string path,
    const spdy::SpdyHeaderBlock& response_headers,
    const QuicStringPiece response_body);
   
 private:
  std::unordered_map<std::string, std::unique_ptr<CacheEntry>> stream_cache; 
};

}

#endif
