#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#include "net/abrcc/dash_config.h"

namespace quic {

AbrInterface* getAbr(
  const std::string& abr_type, 
  const std::shared_ptr<DashBackendConfig>& config,
  const std::string& minerva_config_path_ // only used by Minerva
);

}

#endif
