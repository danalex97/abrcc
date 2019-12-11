#include "net/abrcc/abr/loop.h"

#include <string>

#include "base/bind.h"
#include "base/run_loop.h"
#include "base/task_runner.h"
#include "base/threading/thread.h"
#include "base/threading/thread_task_runner_handle.h"
#include "base/task/task_traits.h"

#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_text_utils.h"

const std::string RESPONSE_PATH = "/";

namespace quic {

AbrLoop::AbrLoop(
    std::unique_ptr<AbrInterface> interface,
    std::shared_ptr<MetricsService> metrics,
    std::shared_ptr<StoreService> store,
    std::shared_ptr<PushService> push
) : interface(std::move(interface)), metrics(metrics), store(store), push(push) {}
AbrLoop::~AbrLoop() { }

static void Push(
  AbrLoop *loop, 
  StoreService::QualifiedResponse qualified_response,
  bool* wasPushed,
  bool* done,
  std::string piece_id
) {
  auto* response = qualified_response.response;
  bool couldPush = loop->push->PushResponse(
    qualified_response.path,
    qualified_response.host,
    qualified_response.path,
    response->headers(),
    response->body());

  if (couldPush) {
    *wasPushed = true;
    loop->pushed.insert(piece_id);
  }

  *done = true;
}

static void Loop(AbrLoop *loop, const scoped_refptr<base::SingleThreadTaskRunner> runner) {
  while (true) {
    // regsiter metrics
    for (auto& metrics : loop->metrics->GetMetrics()) {
      loop->interface->registerMetrics(*metrics);
    }

    // get decision
    auto decision = loop->interface->decide();  

    // check if decision is not new
    if (loop->pushed.find(decision.Id()) != loop->pushed.end()) {
      continue;
    }

    QUIC_LOG(INFO) << "[AbrLoop] New decision: " << decision.index << ":" << decision.quality;
    
    bool wasPushed = false;
    while (!wasPushed) {
      auto qualified_response = loop->store->GetVideo(decision.index, decision.quality);
      auto* response = qualified_response.response;
      qualified_response.path = "/request/" + std::to_string(decision.index);

      if (response != nullptr && loop->pushed.find(decision.Id()) == loop->pushed.end()) {
        bool done = false;

        // post task to the task runner
        runner->PostTask(FROM_HERE,
          base::BindOnce(&Push, loop, qualified_response, &wasPushed, &done, decision.Id()));
    
        while (!done);
      }
    }

  }
}

void AbrLoop::Start() {
  const scoped_refptr<base::SingleThreadTaskRunner> runner(
    base::ThreadTaskRunnerHandle::Get()
  );

  std::unique_ptr<base::Thread> worker_thread(new base::Thread(""));
  CHECK(worker_thread->Start());

  base::RunLoop run_loop;
  worker_thread->task_runner()->PostTaskAndReply(
    FROM_HERE, base::BindOnce(&Loop, this, runner), run_loop.QuitClosure());

  this->thread = std::move(worker_thread);
}

}
