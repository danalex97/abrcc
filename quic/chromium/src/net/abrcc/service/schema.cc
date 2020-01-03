#include "net/abrcc/service/schema.h"
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
  this->state = rhs.state;
  this->timestamp = rhs.timestamp;
  return *this;
}
Segment::~Segment() {}

Metrics::Metrics() {}
Metrics::~Metrics() {}

DashRequest::DashRequest() {}
DashRequest::~DashRequest() {}

}
