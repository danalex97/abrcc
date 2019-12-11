#include "net/abrcc/abr/loop.h"

namespace quic {

AbrLoop::AbrLoop(
    std::unique_ptr<AbrInterface> interface,
    std::shared_ptr<MetricsService> metrics,
    std::shared_ptr<StoreService> store,
    std::shared_ptr<PushService> push
) : interface(std::move(interface)), metrics(metrics), store(store), push(push) {}
AbrLoop::~AbrLoop() { }
  
void AbrLoop::Start() {
}

}
