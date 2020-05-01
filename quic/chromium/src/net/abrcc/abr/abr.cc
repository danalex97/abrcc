#include "net/abrcc/abr/abr_base.h"
#include "net/abrcc/abr/abr_worthed.h"
#include "net/abrcc/abr/abr_target.h"

#include "net/abrcc/abr/abr.h"


namespace quic {

AbrInterface* getAbr(
  const std::string& abr_type, 
  const std::shared_ptr<DashBackendConfig>& config
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
  }
  QUIC_LOG(WARNING) << "Defaulting to BB abr";
  return new BBAbr(config);
}

}
