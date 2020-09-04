#ifndef ABRCC_ABR_LOOP_H__
#define ABRCC_ABR_LOOP_H_

#include "net/abrcc/abr/interface.h"

#include "net/abrcc/service/metrics_service.h"
#include "net/abrcc/service/poll_service.h"
#include "net/abrcc/service/store_service.h"

#include "base/threading/thread.h"

namespace quic {

// AbrLoop class wrapper. Allows starting and periodically calling the AbrInterface
// implementation into a separate thread. It will provide the AbrInterface with access
// to all the relevant services.
class AbrLoop {
 public:
  AbrLoop(
    std::unique_ptr<AbrInterface> interface,
    std::shared_ptr<MetricsService> metrics,
    std::shared_ptr<PollingService> poll,
    std::shared_ptr<StoreService> store);  
  AbrLoop(const AbrLoop&) = delete;
  AbrLoop& operator=(const AbrLoop&) = delete;
  ~AbrLoop();
  
  void Start();

  std::unique_ptr<AbrInterface> interface;
  std::shared_ptr<MetricsService> metrics;
  std::shared_ptr<PollingService> poll;    
  std::shared_ptr<StoreService> store;

  std::unique_ptr<base::Thread> thread;
  std::unordered_set<std::string> sent;
};

}

#endif
