#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"

#include <unordered_map>

namespace quic {

class SegmentProgressAbr : public AbrInterface {
 public:
  SegmentProgressAbr();
  ~SegmentProgressAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  abr_schema::Decision decide() override;

  virtual int decideQuality(int index) = 0; 
 protected:
  std::unordered_map<int, abr_schema::Segment> last_segment;  
  std::unordered_map<int, abr_schema::Decision> decisions; 
  int decision_index;
  int last_timestamp;
 private:
  void update_segment(abr_schema::Segment segment);
  bool should_send(int index);
};

class RandomAbr : public SegmentProgressAbr {
 public: 
  RandomAbr();
  ~RandomAbr() override;

 int decideQuality(int index) override;
};

class BBAbr : public SegmentProgressAbr {
 public:
  BBAbr();
  ~BBAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;
 private:
  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
};

AbrInterface* getAbr(const std::string& abr_type);

}

#endif
