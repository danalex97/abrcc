#ifndef ABRCC_DASH_SERVER_H_
#define ABRCC_DASH_SERVER_H_

#include "net/third_party/quiche/src/quic/core/crypto/proof_source.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/third_party/quiche/src/quic/tools/quic_spdy_server_base.h"

namespace quic {

class QuicDashServer {
 public:
  class ServerFactory {
   public:
    virtual ~ServerFactory() = default;

    virtual std::unique_ptr<QuicSpdyServerBase> CreateServer(
        QuicSimpleServerBackend* backend,
        std::unique_ptr<ProofSource> proof_source,
        const ParsedQuicVersionVector& supported_versions) = 0;
  };

  class BackendFactory {
   public:
    virtual ~BackendFactory() = default;
    virtual std::unique_ptr<QuicSimpleServerBackend> CreateBackend() = 0;
  };

  class MemoryCacheBackendFactory : public BackendFactory {
   public:
    std::unique_ptr<quic::QuicSimpleServerBackend> CreateBackend() override;
  };

  QuicDashServer(BackendFactory* backend_factory, ServerFactory* server_factory);

  int Start();

 private:
  BackendFactory* backend_factory_; 
  ServerFactory* server_factory_;   
};

}

#endif  
