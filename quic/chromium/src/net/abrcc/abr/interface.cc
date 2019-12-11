#include "net/abrcc/abr/interface.h"

namespace abr_schema {

Decision::Decision(int index, int quality, int timestamp) : index(index)
                                                          , quality(quality)
                                                          , timestamp(timestamp) {}
Decision::Decision() {}
Decision::~Decision() {}
Decision::Decision(const Decision& rhs) : index(rhs.index), quality(rhs.quality)
                                        , timestamp(rhs.timestamp) {}
Decision& Decision::operator =(const Decision& rhs) {
  this->index = rhs.index;
  this->quality = rhs.quality;
  this->timestamp = rhs.timestamp;
  return *this;
}

}

namespace quic {

AbrInterface::~AbrInterface() {}

}
