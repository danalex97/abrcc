#include "net/abrcc/abr/abr.h"
#include "net/abrcc/abr/schema.h"

namespace quic {

AbrInterface::~AbrInterface() {}

AbrRandom::AbrRandom() {}
AbrRandom::~AbrRandom() {}

void AbrRandom::registerMetrics(const abr_schema::Metrics &) { 
  // [TODO] implement
}

abr_schema::Decision AbrRandom::decide() { 
  // [TODO] implement
  return abr_schema::Decision(0, 0, 0);
}


}
