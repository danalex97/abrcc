#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#include "net/abrcc/dash_config.h"

namespace quic {

AbrInterface* getAbr(
  const std::string& abr_type, 
  const std::shared_ptr<DashBackendConfig>& config
);

}

#endif
