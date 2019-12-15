#include "net/abrcc/abr/abr.h"
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include <algorithm>

// Qualities: 0 -> 5
const int QUALITIES = 6;

namespace quic {

AbrRandom::AbrRandom() : last_index(0), last_timestamp(0) {}
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
  //if (last_index == 0) {
  random_quality = 1;
  //}
  if (decisions.find(last_index + 1) == decisions.end()) {
    // decisions should be idempotent
    decisions[last_index + 1] = abr_schema::Decision(
      last_index + 1, 
      random_quality, 
      last_timestamp
    );
  }
  int next_index = last_index + 1;
  // [TODO] is this ok?
  last_index = next_index;
  return decisions[next_index];
}

}
