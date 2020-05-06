#ifndef ABRCC_ABR_ABR_GAP_H_
#define ABRCC_ABR_ABR_GAP_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// dependencies on other abr algorithms
#include "net/abrcc/abr/abr_target.h" // TargetAbr2

// data structure deps
#include "net/abrcc/dash_config.h"

// interfaces
#include "net/abrcc/abr/interface.h"


namespace quic {

class GapAbr : public TargetAbr2 {
 public:
  GapAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~GapAbr() override;
 
  int decideQuality(int index) override;  
};

}


#pragma GCC diagnostic pop

#endif
