#ifndef ABRCC_ABR_DASH_API_H_
#define ABRCC_ABR_DASH_API_H_

#include "net/abrcc/abr/abr.h"

#include "net/third_party/quiche/src/quic/platform/api/quic_string_piece.h"
#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"

namespace quic {

class DashApi {
 public:
  DashApi(std::unique_ptr<AbrInterface> abr);
  DashApi(const DashApi&) = delete;
  DashApi& operator=(const DashApi&) = delete;
  ~DashApi();

  void FetchResponseFromBackend(
      const spdy::SpdyHeaderBlock& request_headers,
      const std::string& request_body,
      QuicSimpleServerBackend::RequestHandler* quic_server_stream);
 private:
  std::unique_ptr<AbrInterface> abr;
};

}

#endif
