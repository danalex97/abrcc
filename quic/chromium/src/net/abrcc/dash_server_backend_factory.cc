#include "net/abrcc/dash_server_backend_factory.h"

namespace net {

std::unique_ptr<quic::QuicSimpleServerBackend>
QuicSimpleServerBackendFactory::CreateBackend() {  
  quic::QuicDashServer::MemoryCacheBackendFactory backend_factory;
  return backend_factory.CreateBackend();
}

}  
