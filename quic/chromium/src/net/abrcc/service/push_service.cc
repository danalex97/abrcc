#include "net/abrcc/service/push_service.h"

#include <string>
#include <unordered_map>

#include "net/third_party/quiche/src/quic/core/http/spdy_utils.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_text_utils.h"

namespace quic {

PushService::PushService() {}
PushService::~PushService() {}

void PushService::RegisterPath(
  const spdy::SpdyHeaderBlock& request_headers,
  const std::string& request_body,
  QuicSimpleServerBackend::RequestHandler* quic_server_stream
) {
  // the stream's path is used as the PUSH base 
  auto pathWrapper = request_headers.find(":path");
  if (pathWrapper != request_headers.end()) {
    // add path to cache if not present
    auto path = pathWrapper->second.as_string();
    if (stream_cache.find(path) == stream_cache.end()) {
      std::unique_ptr<CacheEntry> entry(
        new CacheEntry(request_headers, request_body, quic_server_stream)
      );
      stream_cache[path] = std::move(entry);
    }
  }
}

bool PushService::PushResponse(
  const std::string request_path,
  const std::string host,
  const std::string path,
  const spdy::SpdyHeaderBlock& response_headers,
  const QuicStringPiece response_body
) {
  auto entry = stream_cache.find(request_path);
  if (entry != stream_cache.end()){
    QUIC_LOG(INFO) << "Pushing entry [" << host << ", " << path << "]";

    entry->second->handler->PushResponse(entry->second->base_request_headers->Clone());
/*
    std::list<QuicBackendResponse::ServerPushInfo> push_resources;
    push_resources.push_back(QuicBackendResponse::ServerPushInfo(
      QuicUrl(host + path), response_headers.Clone(), 0, "muie"
    ));

    QuicBackendResponse dummy;
    dummy.set_response_type(QuicBackendResponse::IGNORE_REQUEST);

    entry->second->handler->OnResponseBackendComplete(&dummy, push_resources);
*/
    return true;
  } else {
    QUIC_LOG(INFO) << "Failed to push resource: cache entry not found";
    return false;
  }
}
   
PushService::CacheEntry::CacheEntry(
  const spdy::SpdyHeaderBlock& request_headers,
  const std::string request_body,
  QuicSimpleServerBackend::RequestHandler* handler
) : base_request_headers(std::make_unique<spdy::SpdyHeaderBlock>(request_headers.Clone()))
  , request_body(request_body)
  , handler(handler) {}
PushService::CacheEntry::~CacheEntry() {}

}
