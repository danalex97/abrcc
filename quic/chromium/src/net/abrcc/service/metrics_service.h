#ifndef ABRCC_SERVICE_METRICS_H_
#define ABRCC_SERVICE_METRICS_H_

#include "net/abrcc/service/schema.h"

#include "net/third_party/quiche/src/quic/platform/api/quic_string_piece.h"
#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"

namespace quic {

// !THREAD_UNSAFE
class MetricsService {
 public:
  MetricsService();
  MetricsService(const MetricsService&) = delete;
  MetricsService& operator=(const MetricsService&) = delete;
  ~MetricsService();

  // Add new metrics from a request
  void AddMetrics(
      const spdy::SpdyHeaderBlock& request_headers,
      const std::string& request_body,
      QuicSimpleServerBackend::RequestHandler* quic_server_stream);
  
  // Get all registered metrics so far
  std::vector<std::unique_ptr<abr_schema::Metrics>> GetMetrics();
 
 private:
  void AddMetricsImpl(abr_schema::Metrics* metrics);
  std::vector<std::unique_ptr<abr_schema::Metrics>> metrics;
};

}

#endif
