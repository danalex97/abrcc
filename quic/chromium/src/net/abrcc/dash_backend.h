#ifndef ABRCC_DASH_BACKEND_H_
#define ABRCC_DASH_BACKEND_H_

#include "net/abrcc/abr/interface.h"

#include "net/abrcc/service/store_service.h"
#include "net/abrcc/service/metrics_service.h"
#include "net/abrcc/service/push_service.h"

#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"

namespace quic {

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
  std::shared_ptr<StoreService> store;
  std::shared_ptr<MetricsService> metrics_service;
  std::shared_ptr<PushService> push_service;

  bool backend_initialized_;
  
  std::unique_ptr<AbrInterface> abr;
};

}  

#endif  
