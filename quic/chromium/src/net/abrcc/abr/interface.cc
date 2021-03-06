#include "net/abrcc/abr/interface.h"
#include <string>

namespace abr_schema {

Decision::Decision(int index, int quality, int timestamp) : index(index)
                                                          , quality(quality)
                                                          , timestamp(timestamp) {}
Decision::Decision() : index(-1), quality(-1), timestamp(-1) {}
Decision::~Decision() {}
Decision::Decision(const Decision& rhs) : index(rhs.index), quality(rhs.quality)
                                        , timestamp(rhs.timestamp) {}
Decision& Decision::operator =(const Decision& rhs) {
  this->index = rhs.index;
  this->quality = rhs.quality;
  this->timestamp = rhs.timestamp;
  return *this;
}

std::string Decision::path() {
  return "/request/" + std::to_string(index);
}

std::string Decision::resourcePath() {
  return "/piece/" + std::to_string(index);
}

std::string Decision::videoPath() {
  return "/video" + std::to_string(quality) + "/" + std::to_string(index) + ".m4s"; 
}

std::string Decision::serialize() {
  std::stringstream out;
  out << "{";
  out << "\"index\":" << this->index << ",";
  out << "\"quality\":" << this->quality << ",";
  out << "\"timestamp\":" << this->timestamp;
  out << "}";
  return out.str();
}

bool Decision::noop() {
  return index == -1 && quality == -1 && timestamp == -1;
}

}

namespace quic {

AbrInterface::~AbrInterface() {}

}
