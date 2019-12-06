#ifndef ABRCC_ABR_SCHEMA_H_
#define ABRCC_ABR_SCHEMA_H_

#include "base/json/json_value_converter.h"

namespace abr_schema {

struct Value {
  int value;
  int timestamp;

  Value();
  Value(const Value&);
  Value& operator=(const Value&);
  ~Value();

  static void RegisterJSONConverter(base::JSONValueConverter<Value>* converter) {
    converter->RegisterIntField("value", &Value::value);
    converter->RegisterIntField("timestamp", &Value::timestamp);
  }
};

struct Segment {
  int index;
  int quality;
  int timestamp;
  std::string state;

  Segment();
  Segment(const Segment&);
  Segment& operator=(const Segment&);
  ~Segment();

  static void RegisterJSONConverter(base::JSONValueConverter<Segment>* converter) {
    converter->RegisterIntField("index", &Segment::index);
    converter->RegisterIntField("quality", &Segment::quality);
    converter->RegisterIntField("timestamp", &Segment::timestamp);
    converter->RegisterStringField("state", &Segment::state);
  }
};

struct Metrics {
  std::vector<std::unique_ptr<Value>> droppedFrames;
  std::vector<std::unique_ptr<Value>> playerTime;
  std::vector<std::unique_ptr<Value>> bufferLevel;
  std::vector<std::unique_ptr<Segment>> segments; 

  Metrics();
  Metrics(const Metrics&) = delete;
  Metrics& operator=(const Metrics&) = delete;
  ~Metrics();

  static void RegisterJSONConverter(base::JSONValueConverter<Metrics>* converter) {
    converter->RegisterRepeatedMessage<Value>("droppedFrames", &Metrics::droppedFrames);
    converter->RegisterRepeatedMessage<Value>("playerTime", &Metrics::playerTime);
    converter->RegisterRepeatedMessage<Value>("bufferLevel", &Metrics::bufferLevel);
    converter->RegisterRepeatedMessage<Segment>("segments", &Metrics::segments);
  }
};

struct DashRequest {
  Metrics metrics;
  bool piggyback;

  DashRequest();
  DashRequest(const DashRequest&) = delete;
  DashRequest& operator=(const DashRequest&) = delete;
  ~DashRequest();

  static void RegisterJSONConverter(base::JSONValueConverter<DashRequest>* converter) {
    converter->RegisterNestedField<Metrics>("stats", &DashRequest::metrics);
    converter->RegisterBoolField("pieceRequest", &DashRequest::piggyback);
  }
};

struct Decision {
  int index;
  int quality;
  int timestamp;

  Decision();
  Decision(int index, int quality, int timestamp);
  Decision(const Decision&);
  Decision& operator=(const Decision&);
  ~Decision();

  std::string serialize();
};

}

#endif  
