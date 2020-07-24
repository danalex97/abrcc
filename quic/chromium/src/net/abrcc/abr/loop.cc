#include "net/abrcc/abr/loop.h"

#include <string>
#include <chrono>
#include <thread>

#include "base/bind.h"
#include "base/run_loop.h"
#include "base/task_runner.h"
#include "base/threading/thread.h"
#include "base/threading/thread_task_runner_handle.h"
#include "base/task/task_traits.h"

#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_text_utils.h"

using spdy::SpdyHeaderBlock;

namespace quic {

AbrLoop::AbrLoop(
  std::unique_ptr<AbrInterface> interface,
  std::shared_ptr<MetricsService> metrics,
  std::shared_ptr<PollingService> poll,
  std::shared_ptr<StoreService> store
) : interface(std::move(interface)), metrics(metrics), poll(poll), store(store) {}
AbrLoop::~AbrLoop() { }

static void Respond(
  AbrLoop *loop, 
  bool* sent,
  bool* done,
  abr_schema::Decision decision
) {
  bool couldRespond = loop->poll->SendResponse(
    decision.path(),
    decision.serialize());
  if (couldRespond) {
    *sent = true;
    loop->sent.insert(decision.path());
  }
  *done = true;
}

static void SendPiece(
  AbrLoop *loop, 
  bool* sent,
  bool* done,
  abr_schema::Decision decision
) {
  auto entry = loop->poll->GetEntry(decision.resourcePath());
  if (entry) {
    *sent = true;
    loop->sent.insert(decision.resourcePath());
      
    // modify requeest headers to match with the Store
    SpdyHeaderBlock request_headers(entry->base_request_headers->Clone());
    request_headers[":path"] = decision.videoPath();

    // fetch response from store
    loop->store->FetchResponseFromBackend(
      request_headers.Clone(),
      entry->request_body,
      entry->handler);
  }
  *done = true;
}

static void Loop(AbrLoop *loop, const scoped_refptr<base::SingleThreadTaskRunner> runner) {
  while (true) {
    // register metrics
    for (auto& metrics : loop->metrics->GetMetrics()) {
      loop->interface->registerMetrics(*metrics);
    }

    // register aborts
    for (auto& abort : loop->metrics->GetAborts()) {
      loop->interface->registerAbort(abort);
    }

    // get decision
    auto decision = loop->interface->decide(); 
    
    // sleep if decision is noop; this means that we only register metrics
    // and call the function loop->interface->decide function every 20ms
    if (decision.noop()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
      continue;
    }
    
    if (loop->sent.find(decision.path()) == loop->sent.end()) {
      bool sent = false;
      while (!sent) {
        if (loop->sent.find(decision.path()) == loop->sent.end()) {
          bool done = false;
          runner->PostTask(FROM_HERE,
            base::BindOnce(&Respond, loop, &sent, &done, decision));
          while (!done);
        }
        
        if (!sent) {
          std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
      }
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }

    if (loop->sent.find(decision.resourcePath()) == loop->sent.end()) {
      bool sent = false;
      while (!sent) {
        if (loop->sent.find(decision.resourcePath()) == loop->sent.end()) {
          bool done = false;
          runner->PostTask(FROM_HERE,
            base::BindOnce(&SendPiece, loop, &sent, &done, decision));
          while (!done);
        }
        
        if (!sent) {
          std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
      }
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
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
