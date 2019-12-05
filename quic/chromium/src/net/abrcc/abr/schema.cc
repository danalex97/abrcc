#include "net/abrcc/abr/schema.h"
#include <sstream>

namespace abr_schema {

Value::Value() {}
Value::Value(const Value& rhs) : value(rhs.value), timestamp(rhs.timestamp) {}
Value& Value::operator =(const Value& rhs) {
  this->value = rhs.value;
  this->timestamp = rhs.timestamp;
  return *this;
}
Value::~Value() {}

Segment::Segment() {}
Segment::Segment(const Segment& rhs) : index(rhs.index), quality(rhs.quality),
                                       timestamp(rhs.timestamp), state(rhs.state) {}
Segment& Segment::operator =(const Segment& rhs) {
  this->index = rhs.index; 
  this->quality = rhs.quality;
  this->state = rhs.state;
  this->timestamp = rhs.timestamp;
  return *this;
}
Segment::~Segment() {}

Metrics::Metrics() {}
Metrics::~Metrics() {}

DashRequest::DashRequest() {}
DashRequest::~DashRequest() {}

Decision::Decision(int index, int quality, int timestamp) : index(index)
                                                          , quality(quality)
                                                          , timestamp(timestamp) {}
Decision::~Decision() {}
Decision::Decision(const Decision& rhs) : index(rhs.index), quality(rhs.quality)
                                        , timestamp(rhs.timestamp) {}
Decision& Decision::operator =(const Decision& rhs) {
  this->index = rhs.index;
  this->quality = rhs.quality;
  this->timestamp = rhs.timestamp;
  return *this;
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

}
