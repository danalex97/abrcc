#ifndef ABRCC_DASH_SERVER_BACKEND_FACTORY_H_
#define ABRCC_DASH_SERVER_BACKEND_FACTORY_H_

#include "net/abrcc/dash_server.h"

namespace net {

class QuicSimpleServerBackendFactory : public quic::QuicDashServer::BackendFactory {
 public:
  std::unique_ptr<quic::QuicSimpleServerBackend> CreateBackend() override;
};

} 

#endif
