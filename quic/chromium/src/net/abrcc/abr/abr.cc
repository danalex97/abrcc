#include "net/abrcc/abr/abr_base.h"
#include "net/abrcc/abr/abr_worthed.h"
#include "net/abrcc/abr/abr_target.h"
#include "net/abrcc/abr/abr_gap.h"
#include "net/abrcc/abr/abr_minerva.h"
#include "net/abrcc/abr/abr_remote.h"

#include "net/abrcc/abr/abr.h"


namespace quic {

AbrInterface* getAbr(
  const std::string& abr_type, 
  const std::shared_ptr<DashBackendConfig>& config,
  const std::string& minerva_config_path_ // only used by Minerva
) {
  if (abr_type == "bb") {
    QUIC_LOG(WARNING) << "BB abr selected";
    return new BBAbr(config);
  } else if (abr_type == "random") {
    QUIC_LOG(WARNING) << "Random abr selected";
    return new RandomAbr(config);
  } else if (abr_type == "worthed") {
    QUIC_LOG(WARNING) << "Worthed abr selected";
    return new WorthedAbr(config);
  } else if (abr_type == "target") {
    QUIC_LOG(WARNING) << "Target abr selected";
    return new TargetAbr(config);
  } else if (abr_type == "target2") {
    QUIC_LOG(WARNING) << "Target2 abr selected";
    return new TargetAbr2(config);
  } else if (abr_type == "target3") {
    QUIC_LOG(WARNING) << "Target3 abr selected";
    return new TargetAbr3(config);
  } else if (abr_type == "gap") {
    QUIC_LOG(WARNING) << "Gap abr selected";
    return new GapAbr(config);
  } else if (abr_type == "remote") {
    QUIC_LOG(WARNING) << "Remote abr selected";
    return new RemoteAbr(config);
  } else if (abr_type == "minerva") {
    QUIC_LOG(WARNING) << "Minerva abr selected";
    return new MinervaAbr(config, minerva_config_path_);
  }
  QUIC_LOG(WARNING) << "Defaulting to BB abr";
  return new BBAbr(config);
}

}
