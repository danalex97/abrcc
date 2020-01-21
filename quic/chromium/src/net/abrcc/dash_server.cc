#include "net/abrcc/dash_server.h"

#include <utility>
#include <vector>

#include "net/abrcc/cc/cc_selector.h"

#include "net/abrcc/dash_backend.h"
#include "net/third_party/quiche/src/quic/core/quic_versions.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_default_proof_providers.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flags.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_socket_address.h"

DEFINE_QUIC_COMMAND_LINE_FLAG(int32_t,
                              port,
                              6121,
                              "The port the quic server will listen on.");

DEFINE_QUIC_COMMAND_LINE_FLAG(
    std::string,
    quic_config_path,
    "",
    "Specifies the path to the JSON configuration path of the"
    "quic server. In the JSON we should specify the paths for"
    "videos and the DASH manifest.");
DEFINE_QUIC_COMMAND_LINE_FLAG(
    std::string,
    site,
    "",
    "Site.");
DEFINE_QUIC_COMMAND_LINE_FLAG(
    std::string,
    cc_type,
    "bbr",
    "Congestion contorl type.");

namespace quic {

std::unique_ptr<quic::QuicSimpleServerBackend>
QuicDashServer::MemoryCacheBackendFactory::CreateBackend() {
  auto dash_backend = std::make_unique<DashBackend>();
  if (!GetQuicFlag(FLAGS_quic_config_path).empty()) {
    dash_backend->SetExtra(FLAGS_site);
    dash_backend->InitializeBackend(
      GetQuicFlag(FLAGS_quic_config_path));
  }
  return dash_backend;
}

QuicDashServer::QuicDashServer(BackendFactory* backend_factory,
                               ServerFactory* server_factory)
    : backend_factory_(backend_factory), server_factory_(server_factory) {}

int QuicDashServer::Start() {
  auto *selector = CCSelector::GetInstance();
  selector->setCongestionControlType(GetQuicFlag(FLAGS_cc_type));

  auto supported_versions = AllSupportedVersions();
  for (const auto& version : supported_versions) {
    QuicEnableVersion(version);
  }
  auto proof_source = quic::CreateDefaultProofSource();
  auto backend = backend_factory_->CreateBackend();
  auto server = server_factory_->CreateServer(
      backend.get(), std::move(proof_source), supported_versions);

  auto port = GetQuicFlag(FLAGS_port);
  if (!server->CreateUDPSocketAndListen(quic::QuicSocketAddress(
          quic::QuicIpAddress::Any6(), port))) {
    return 1;
  }

  server->HandleEventsForever();
  return 0;
}

} 
