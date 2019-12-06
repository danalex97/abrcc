#include "net/abrcc/abr/abr.h"
#include "net/abrcc/abr/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include <algorithm>

const int QUALITIES = 6;

namespace quic {

AbrInterface::~AbrInterface() {}

AbrRandom::AbrRandom() {}
AbrRandom::~AbrRandom() {}

void AbrRandom::registerMetrics(const abr_schema::Metrics &metrics) { 
  for (auto& segment : metrics.segments) {
    last_index = std::max(last_index, segment->index); 
    last_timestamp = std::max(last_timestamp, segment->timestamp);
    QUIC_LOG(INFO) << "[AbrRandom] " << segment->timestamp << ' ' << segment->index << '\n';
  }
}

abr_schema::Decision AbrRandom::decide() { 
  int random_quality = rand() % QUALITIES;
  return abr_schema::Decision(
    last_index + 1, 
    random_quality, 
    last_timestamp
  );
}


}
