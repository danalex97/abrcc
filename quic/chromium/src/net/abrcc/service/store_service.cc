#include "net/abrcc/service/store_service.h"

#include <utility>
#include <string>
#include <fstream>
#include <streambuf>

#include "base/json/json_value_converter.h"
#include "base/json/json_reader.h"
#include "base/values.h"

#include "net/abrcc/dash_config.h"
#include "net/third_party/quiche/src/quic/core/http/spdy_utils.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_text_utils.h"

#include "base/bind.h"
#include "base/run_loop.h"
#include "base/task_runner.h"
#include "base/threading/thread.h"

using spdy::SpdyHeaderBlock;

namespace quic { 

StoreService::StoreService() : cache(new QuicMemoryCacheBackend()) {}
StoreService::~StoreService() {}

static void staticRegisterResource(
  quic::StoreService* service,
  const std::string& domain, 
  const std::string& resource_path, 
  const std::string& resource
) {
  QUIC_LOG(INFO) << "[register resource] " << domain << " -> " << resource 
                 << " : " << resource_path;

  std::ifstream stream(resource_path);
  std::string data((std::istreambuf_iterator<char>(stream)),
                    std::istreambuf_iterator<char>());
  
  if (data.size() == 0) {
    std::ifstream stream(resource_path, std::ios::binary);
    std::string bin_data((std::istreambuf_iterator<char>(stream)),
                          std::istreambuf_iterator<char>());
    data = bin_data;  
  }

  QUIC_LOG(INFO) << "[data] " << data.size() << '\n';
  
  SpdyHeaderBlock response_headers;
  response_headers[":status"] = QuicTextUtils::Uint64ToString(200);
  response_headers["content-length"] = QuicTextUtils::Uint64ToString(data.size());
 
  service->cache->AddResponse(domain, resource, std::move(response_headers), data);
}

static void staticRegisterVideo(
  quic::StoreService* service,
  const std::string& domain, 
  const std::string& resource_path, 
  const std::string& resource,
  const int length 
) {
  staticRegisterResource(service, domain, resource_path + "/Header.m4s", resource + "/Header.m4s");
  for (int i = 1; i <= length; ++i) {
    std::string file = "/" + QuicTextUtils::Uint64ToString(i) + ".m4s";
    staticRegisterResource(service, domain, resource_path + file, resource + file);
  }
}

void StoreService::registerResource(
  const std::string& domain, 
  const std::string& resource_path, 
  const std::string& resource
) {
  staticRegisterResource(this, domain, resource_path, resource);
}

void StoreService::registerVideo(
  const std::string& domain, 
  const std::string& resource_path, 
  const std::string& resource,
  const int length 
) {
  staticRegisterVideo(this, domain, resource_path, resource, length); 
}

std::unique_ptr<base::Thread> StoreService::registerVideoAsync(
  const std::string& domain, 
  const std::string& resource_path, 
  const std::string& resource,
  const int length 
) {
  std::unique_ptr<base::Thread> worker_thread(new base::Thread(""));
  CHECK(worker_thread->Start());

  base::RunLoop run_loop;
  worker_thread->task_runner()->PostTaskAndReply(FROM_HERE, base::BindOnce(
    &staticRegisterVideo, this, domain, resource_path, resource, length
  ), run_loop.QuitClosure());

  return worker_thread;
}

StoreService::QualifiedResponse::QualifiedResponse(
  const QuicBackendResponse* response,
  std::string host,
  std::string path) : response(response), host(host), path(path) {}
StoreService::QualifiedResponse::QualifiedResponse(const QualifiedResponse& resp) 
  : response(resp.response), host(resp.host), path(resp.path) {}
StoreService::QualifiedResponse::~QualifiedResponse() {}

StoreService::QualifiedResponse StoreService::GetVideo(const int piece, const int quality) {
  for (const auto& video_config : config->video_configs) {
    std::string resource = video_config->resource;    
    if (resource.find(std::to_string(quality)) != std::string::npos) {
      std::string file = "/" + QuicTextUtils::Uint64ToString(piece) + ".m4s";
      return StoreService::QualifiedResponse(
        cache->GetResponse(config->domain, resource + file),
        config->domain,
        resource + file
      );
    }
  }
  return StoreService::QualifiedResponse(nullptr, "", "");
}


void StoreService::VideoFromConfig(
  const std::string& dir_path, 
  std::shared_ptr<DashBackendConfig> config
) {
  // init
  this->dir_path = dir_path;
  this->config = config;
  
  // add resources
  std::vector<std::unique_ptr<base::Thread>> threads;
  for (const auto& video_config : config->video_configs) {
    std::string resource = video_config->resource;    
    std::string path = dir_path + video_config->path; 
   
    QUIC_LOG(INFO) << "Caching resource " << resource << " at path " << path;
    
    int video_length = 49;
    threads.push_back(
      registerVideoAsync(config->domain, path, resource, video_length)
    );
  }
  for (auto &thread: threads) {
     thread->Stop();
  }
}

void StoreService::MetaFromConfig(
  const std::string& base_path, 
  std::shared_ptr<DashBackendConfig> config
) {
  // init
  this->base_path = base_path;
  this->config = config;
  
  // add resources
  registerResource(config->domain, base_path + config->player_config.index, "/");
  registerResource(
    config->domain, base_path + config->player_config.index, config->player_config.index);
  registerResource(
    config->domain, base_path + config->player_config.manifest, config->player_config.manifest);
  registerResource(
    config->domain, base_path + config->player_config.player, config->player_config.player);
}

void StoreService::FetchResponseFromBackend(
  const SpdyHeaderBlock& request_headers,
  const std::string& string, 
  QuicSimpleServerBackend::RequestHandler* quic_stream
) {
  cache->FetchResponseFromBackend(request_headers, string, quic_stream);
}

}
