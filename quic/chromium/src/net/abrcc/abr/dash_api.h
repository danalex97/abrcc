#ifndef ABRCC_ABR_DASH_API_H_
#define ABRCC_ABR_DASH_API_H_

#include "net/abrcc/abr/schema.h"

#include "net/third_party/quiche/src/quic/platform/api/quic_string_piece.h"
#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"

using spdy::SpdyHeaderBlock;

namespace quic {

class DashApi {
 public:
  DashApi();
  DashApi(const DashApi&) = delete;
  DashApi& operator=(const DashApi&) = delete;
  ~DashApi();

  void FetchResponseFromBackend(
      const spdy::SpdyHeaderBlock& request_headers,
      const std::string& request_body,
      QuicSimpleServerBackend::RequestHandler* quic_server_stream);
 private:
  void registerMetrics(const abr_schema::Metrics &);
};
     
}

#endif
