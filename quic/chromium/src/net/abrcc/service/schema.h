#ifndef ABRCC_SERVICE_SCHEMA_H_
#define ABRCC_SERVICE_SCHEMA_H_

#include "base/json/json_value_converter.h"
#include <optional>

namespace abr_schema {

const int NOT_PRESENT = -1;

struct Value {
  int value;
  int timestamp;

  Value();
  Value(int value, int timestamp);
  Value(const Value&);
  Value& operator=(const Value&);
  ~Value();

  static void RegisterJSONConverter(base::JSONValueConverter<Value>* converter) {
    converter->RegisterIntField("value", &Value::value);
    converter->RegisterIntField("timestamp", &Value::timestamp);
  }
};

struct Segment {
  enum State {
    LOADING, DOWNLOADED, PROGRESS,
  };
 
  int index;
  int timestamp;
  int loaded;
  int total;
  State state;

  Segment();
  Segment(const Segment&);
  Segment& operator=(const Segment&);
  ~Segment();

  static bool ParseState(base::StringPiece value, State* field) {
    if (value == "loading") {
      *field = LOADING;
      return true;
    }
    if (value == "downloaded") {
      *field = DOWNLOADED;
      return true;
    }
    if (value == "progress") {
      *field = PROGRESS;
      return true;
    }
    return false;
  }

  static void RegisterJSONConverter(base::JSONValueConverter<Segment>* converter) {
    converter->RegisterIntField("loaded", &Segment::loaded);
    converter->RegisterIntField("total", &Segment::total);
    converter->RegisterIntField("index", &Segment::index);
    converter->RegisterIntField("timestamp", &Segment::timestamp);
    converter->RegisterCustomField<State>(
      "state", &Segment::state, &ParseState);
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

  DashRequest();
  DashRequest(const DashRequest&) = delete;
  DashRequest& operator=(const DashRequest&) = delete;
  ~DashRequest();

  static void RegisterJSONConverter(base::JSONValueConverter<DashRequest>* converter) {
    converter->RegisterNestedField<Metrics>("stats", &DashRequest::metrics);
  }
};

}

#endif  
