#include "net/abrcc/dash_server.h"

#include <utility>
#include <vector>
#include <iostream>

#include "net/abrcc/cc/cc_selector.h"

#include "net/abrcc/dash_backend.h"
#include "net/third_party/quiche/src/quic/core/quic_versions.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_default_proof_providers.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flags.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_socket_address.h"

#include <stdio.h>
#include <execinfo.h>
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>

DEFINE_QUIC_COMMAND_LINE_FLAG(int32_t,
                              port,
                              6121,
                              "The port the quic server will listen on.");

DEFINE_QUIC_COMMAND_LINE_FLAG(
    std::string,
    minerva_config_path,
    "",
    "Specifies the path to the directory of Minerva configuration"
    "paths. The video structures provided in the directory are used"
    "to compute the PQ normalization curve.");
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
    "Congestion control type.");
DEFINE_QUIC_COMMAND_LINE_FLAG(
    std::string,
    abr_type,
    "bb",
    "Abr type.");

namespace quic {

std::unique_ptr<quic::QuicSimpleServerBackend>
QuicDashServer::MemoryCacheBackendFactory::CreateBackend() {
  auto dash_backend = std::make_unique<DashBackend>(
    FLAGS_abr_type, FLAGS_quic_config_path, FLAGS_site, FLAGS_minerva_config_path
  );
  if (!GetQuicFlag(FLAGS_quic_config_path).empty()) {
    dash_backend->InitializeBackend(
      GetQuicFlag(FLAGS_quic_config_path));
  }
  return dash_backend;
}

void sigsegv_handler(int sig) {
  void *array[10];
  size_t size;

  size = backtrace(array, 10);
  fprintf(stderr, "Error: signal %d:\n", sig);
  backtrace_symbols_fd(array, size, STDERR_FILENO);
}

QuicDashServer::QuicDashServer(BackendFactory* backend_factory,
                               ServerFactory* server_factory)
    : backend_factory_(backend_factory), server_factory_(server_factory) {}

int QuicDashServer::Start() {
  // Add signal handler for exceptions
  signal(SIGSEGV, sigsegv_handler); 

  // Set the CCSelector singleton's congestion control type
  auto *selector = CCSelector::GetInstance();
  selector->setCongestionControlType(GetQuicFlag(FLAGS_cc_type));

  // Create a server with the DASH backend handler from the factory 
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

  // start the handler
  server->HandleEventsForever();
  return 0;
}

} 
