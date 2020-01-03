#include "net/abrcc/abr/abr.h"
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_logging.h"

#include <algorithm>

// Qualities: 0 -> 5
const int QUALITIES = 6;

namespace quic {

AbrRandom::AbrRandom() : decision_index(1), last_timestamp(0) {}
AbrRandom::~AbrRandom() {}

static void log_segment(abr_schema::Segment &segment) {
  switch (segment.state) {
    case abr_schema::Segment::PROGRESS:
      QUIC_LOG(WARNING) << "segment " << segment.index 
                        << " [progress] " << 1.0 * segment.loaded / segment.total;
      break;
    case abr_schema::Segment::DOWNLOADED:
      QUIC_LOG(WARNING) << "segment " << segment.index << " [downloaded]";
      break;
    case abr_schema::Segment::LOADING:
      QUIC_LOG(WARNING) << "segment " << segment.index << " [loading]";
      break;
  }
}

void AbrRandom::update_segment(abr_schema::Segment segment) {
  last_segment[segment.index] = segment;
  
  QUIC_LOG(WARNING) << "[segment update @ " << segment.index << "]";
  log_segment(segment);
}

void AbrRandom::registerMetrics(const abr_schema::Metrics &metrics) {
  QUIC_LOG(WARNING) << "Register metrics";
  for (auto& segment : metrics.segments) {
    log_segment(*segment);
    last_timestamp = std::max(last_timestamp, segment->timestamp);

    switch(segment->state) {
      case abr_schema::Segment::LOADING:
        update_segment(*segment);
        break;
      case abr_schema::Segment::DOWNLOADED:
        if (last_segment.find(segment->index) == last_segment.end() ||
            last_segment[segment->index].state == abr_schema::Segment::PROGRESS) {
          update_segment(*segment);
        }
        break;
      case abr_schema::Segment::PROGRESS:
        if (last_segment.find(segment->index) == last_segment.end() || (
              last_segment[segment->index].state == abr_schema::Segment::PROGRESS &&
              last_segment[segment->index].timestamp < segment->timestamp)) {
          update_segment(*segment);
        }
        break;  
    }
  }
}

bool AbrRandom::should_send(int index) {
  if (index == 1) {
    return true;
  }

  if (last_segment.find(index - 1) == last_segment.end()) {
    // no stats from previous segment
    return false;
  }

  auto segment = last_segment[index - 1];
  if (segment.state != abr_schema::Segment::PROGRESS) {
    // segment has already been downloaded or loaded
    return true;
  }
  
  if (1.0 * segment.loaded / segment.total >= 0.8) {
    // segment has been downloaded more than 80%
    return true;
  }

  return false;
}

abr_schema::Decision AbrRandom::decide() { 
  int random_quality = rand() % QUALITIES;
  int to_decide = decision_index;
  if (to_decide == 1) {
    random_quality = 1;
  }
  
  if (decisions.find(to_decide) == decisions.end() && should_send(to_decide)) {
    // decisions should be idempotent
    decisions[to_decide] = abr_schema::Decision(
      to_decide, 
      random_quality, 
      last_timestamp
    );
    decision_index += 1;

    QUIC_LOG(WARNING) << "[AbrRandom] new decision: [index] " << decisions[to_decide].index
                      << " [quality] " << decisions[to_decide].quality;
    return decisions[to_decide];
  } else {
    return decisions[to_decide - 1];
  }
}

}
