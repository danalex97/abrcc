#ifndef ABRCC_DASH_BACKEND_H_
#define ABRCC_DASH_BACKEND_H_

#include "net/abrcc/abr/loop.h"

#include "net/abrcc/service/store_service.h"
#include "net/abrcc/service/metrics_service.h"
#include "net/abrcc/service/poll_service.h"

#include "net/third_party/quiche/src/quic/tools/quic_backend_response.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_url.h"

namespace quic {

class DashBackend : public QuicSimpleServerBackend {
 public:
  // Note we need the config path for abr
  DashBackend(
    const std::string& abr_type, 
    const std::string& config_path,
    const std::string& site,
    const std::string& minerva_config_path_ // only used by Minerva
  );
  DashBackend(const DashBackend&) = delete;
  DashBackend& operator=(const DashBackend&) = delete;
  ~DashBackend() override;

  // Implements the functions for interface QuicSimpleServerBackend
  bool InitializeBackend(const std::string& _unused) override;
  bool IsBackendInitialized() const override;
  void FetchResponseFromBackend(
      const spdy::SpdyHeaderBlock& request_headers,
      const std::string& request_body,
      QuicSimpleServerBackend::RequestHandler* quic_server_stream) override;
  void CloseBackendResponseStream(
      QuicSimpleServerBackend::RequestHandler* quic_server_stream) override;
 private:
  std::string config_path;
  std::string site;

  std::shared_ptr<StoreService> store;
  std::shared_ptr<MetricsService> metrics;
  std::shared_ptr<PollingService> polling;
  
  std::shared_ptr<DashBackendConfig> config;

  bool backend_initialized_;
  
  std::unique_ptr<AbrLoop> abr_loop;
};

}  

#endif  
