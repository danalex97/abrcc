#include "net/abrcc/abr/interface.h"
#include <string>

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

std::string Decision::Id() {
  return std::to_string(index) + ":" + std::to_string(quality);
}

}

namespace quic {

AbrInterface::~AbrInterface() {}

}
