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

// interface of Gap CC
#include "net/abrcc/cc/gap.h"


namespace quic {

class GapAbr : public TargetAbr2 {
 public:
  GapAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~GapAbr() override;
 
  void registerMetrics(const abr_schema::Metrics &metrics) override;
  int decideQuality(int index) override;  
 
 private:
  // We use both BbrTarget::BbrInterface and BbrGap::gap_interface since we want
  // to allow both CC operation modes.
  BbrGap::BbrInterface* gap_interface; 
};

}


#pragma GCC diagnostic pop

#endif
