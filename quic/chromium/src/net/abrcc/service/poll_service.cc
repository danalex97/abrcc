#include "net/abrcc/service/poll_service.h"

#include <string>
#include <unordered_map>

#include "net/third_party/quiche/src/quic/core/http/spdy_utils.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_mutex.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_text_utils.h"

using spdy::SpdyHeaderBlock;

namespace quic {

PollingService::PollingService() {}
PollingService::~PollingService() {}

void PollingService::AddRequest(
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
    
      QuicWriterMutexLock lock(&mutex_);
      stream_cache[path] = std::move(entry);
    }
  }
}

bool PollingService::SendResponse(
  const std::string request_path,
  const QuicStringPiece response_body
) {
  auto entry = stream_cache.find(request_path);
  if (entry != stream_cache.end()){
    SpdyHeaderBlock response_headers;
    response_headers[":status"] = QuicTextUtils::Uint64ToString(200);
    response_headers["content-length"] = QuicTextUtils::Uint64ToString(response_body.length());
    
    auto* quic_response = new QuicBackendResponse(); 
    quic_response->set_response_type(QuicBackendResponse::REGULAR_RESPONSE);
    quic_response->set_headers(std::move(response_headers));
    quic_response->set_body(response_body);
    quic_response->set_trailers(SpdyHeaderBlock());
    quic_response->set_stop_sending_code(0);

    auto push_info = std::list<QuicBackendResponse::ServerPushInfo>();
    entry->second->handler->OnResponseBackendComplete(quic_response, push_info);

    QuicWriterMutexLock lock(&mutex_);
    stream_cache.erase(request_path);
    return true;
  } else {
    return false;
  }
}


std::unique_ptr<PollingService::CacheEntry> PollingService::GetEntry(
  const std::string request_path
) {  
  auto entry = stream_cache.find(request_path);
  if (entry != stream_cache.end()){
    std::unique_ptr<PollingService::CacheEntry> ret(std::move(entry->second));
    
    QuicWriterMutexLock lock(&mutex_);
    stream_cache.erase(request_path);

    return ret;
  } else {
    return std::unique_ptr<PollingService::CacheEntry>(nullptr);
  }
}


PollingService::CacheEntry::CacheEntry(
  const spdy::SpdyHeaderBlock& request_headers,
  const std::string request_body,
  QuicSimpleServerBackend::RequestHandler* handler
) : base_request_headers(std::make_unique<spdy::SpdyHeaderBlock>(request_headers.Clone()))
  , request_body(request_body)
  , handler(handler) {}
PollingService::CacheEntry::~CacheEntry() {}

}
