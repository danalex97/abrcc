#include "net/abrcc/service/schema.h"
#include <sstream>
#include <optional>

namespace abr_schema {

Value::Value() {}
Value::Value(const Value& rhs) : value(rhs.value), timestamp(rhs.timestamp) {}
Value& Value::operator =(const Value& rhs) {
  this->value = rhs.value;
  this->timestamp = rhs.timestamp;
  return *this;
}
Value::~Value() {}

Segment::Segment() {
  loaded = NOT_PRESENT;
  total = NOT_PRESENT;
}
Segment::Segment(const Segment& rhs) : index(rhs.index), timestamp(rhs.timestamp), 
                                       loaded(rhs.loaded), total(rhs.total),
                                       state(rhs.state) {}
Segment& Segment::operator =(const Segment& rhs) {
  this->index = rhs.index; 
  this->state = rhs.state;
  this->timestamp = rhs.timestamp;
  this->loaded = rhs.loaded;
  this->total = rhs.total;
  return *this;
}
Segment::~Segment() {}

Metrics::Metrics() {}
Metrics::~Metrics() {}

DashRequest::DashRequest() {}
DashRequest::~DashRequest() {}

}
