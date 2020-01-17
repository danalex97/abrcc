#include <vector>

#include "net/abrcc/dash_server.h"
#include "net/abrcc/dash_server_backend_factory.h"
#include "net/third_party/quiche/src/quic/core/quic_versions.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flags.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_ptr_util.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_system_event_loop.h"
#include "net/third_party/quiche/src/quic/tools/quic_simple_server_backend.h"
#include "net/tools/quic/quic_simple_server.h"

const int MAX_STREAMS = 1000000;

class QuicSimpleServerFactory : public quic::QuicDashServer::ServerFactory {
  std::unique_ptr<quic::QuicSpdyServerBase> CreateServer(
      quic::QuicSimpleServerBackend* backend,
      std::unique_ptr<quic::ProofSource> proof_source,
      const quic::ParsedQuicVersionVector& supported_versions) override {
   
    // Allow more streams
    config_.SetMaxIncomingBidirectionalStreamsToSend(MAX_STREAMS);
    config_.SetMaxIncomingUnidirectionalStreamsToSend(MAX_STREAMS);

    return std::make_unique<net::QuicSimpleServer>(
        std::move(proof_source), config_,
        quic::QuicCryptoServerConfig::ConfigOptions(), supported_versions,
        backend);
  }

 private:
  quic::QuicConfig config_;
};

int main(int argc, char* argv[]) {
  QuicSystemEventLoop event_loop("quic_server");
  const char* usage = "Usage: quic_server [options]";
  std::vector<std::string> non_option_args =
      quic::QuicParseCommandLineFlags(usage, argc, argv);
  if (!non_option_args.empty()) {
    quic::QuicPrintCommandLineFlagHelp(usage);
    exit(0);
  }

  net::QuicSimpleServerBackendFactory backend_factory;
  QuicSimpleServerFactory server_factory;
  quic::QuicDashServer server(&backend_factory, &server_factory);
  return server.Start();
}
