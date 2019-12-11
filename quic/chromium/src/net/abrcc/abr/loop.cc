#include "net/abrcc/abr/loop.h"

#include <string>

#include "base/bind.h"
#include "base/run_loop.h"
#include "base/task_runner.h"
#include "base/threading/thread.h"

#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

const std::string RESPONSE_PATH = "/";

namespace quic {

AbrLoop::AbrLoop(
    std::unique_ptr<AbrInterface> interface,
    std::shared_ptr<MetricsService> metrics,
    std::shared_ptr<StoreService> store,
    std::shared_ptr<PushService> push
) : interface(std::move(interface)), metrics(metrics), store(store), push(push) {}
AbrLoop::~AbrLoop() { }

static void Loop(AbrLoop *loop) {  
  while (true) {
    // regsiter metrics
    for (auto& metrics : loop->metrics->GetMetrics()) {
      loop->interface->registerMetrics(*metrics);
    }

    // get decision
    auto decision = loop->interface->decide();  
    QUIC_LOG(INFO) << "[AbrLoop] New decision: " << decision.index << ":" << decision.quality;

    bool wasPushed = false;
    while (!wasPushed) {
      auto qualified_response = loop->store->GetVideo(decision.index, decision.quality);
      auto* response = qualified_response.response;
    
      std::string piece_id = qualified_response.host + ":" + qualified_response.path;
      if (response != nullptr && loop->pushed.find(piece_id) == loop->pushed.end()) {
        bool couldPush = loop->push->PushResponse(
          RESPONSE_PATH,
          qualified_response.host,
          qualified_response.path,
          response->headers(),
          response->body());

        if (couldPush) {
          wasPushed = true;
          loop->pushed.insert(piece_id);
          
          QUIC_LOG(INFO) << "[AbrLoop] Successful push " << piece_id;
        }
      }
    }
  }
}

void AbrLoop::Start() {
  std::unique_ptr<base::Thread> worker_thread(new base::Thread(""));
  CHECK(worker_thread->Start());

  base::RunLoop run_loop;
  worker_thread->task_runner()->PostTaskAndReply(
    FROM_HERE, base::BindOnce(&Loop, this), run_loop.QuitClosure());

  this->thread = std::move(worker_thread);
}

}
