#ifndef ABRCC_ABR_ABR_BASE_H_
#define ABRCC_ABR_ABR_BASE_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// data structure deps
#include "net/abrcc/dash_config.h"

#include <unordered_map>
#include <vector>

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/bbr_adapter.h"


namespace quic {

class SegmentProgressAbr : public AbrInterface {
 public:
  SegmentProgressAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~SegmentProgressAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  abr_schema::Decision decide() override;

  virtual int decideQuality(int index) = 0; 
 protected:
  const std::shared_ptr<DashBackendConfig>& config;
  std::unordered_map<int, abr_schema::Segment> last_segment;  
  std::unordered_map<int, abr_schema::Decision> decisions; 
  
  int decision_index;
  int last_timestamp;
  int last_segment_time_length;

  std::vector< std::vector<VideoInfo> > segments;
  std::vector<int> bitrate_array;
 private:
  void update_segment(abr_schema::Segment segment);
  bool should_send(int index);
};

class RandomAbr : public SegmentProgressAbr {
 public: 
  RandomAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~RandomAbr() override;

 int decideQuality(int index) override;
};

class BBAbr : public SegmentProgressAbr {
 public:
  BBAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~BBAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;
 private:
  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
};

}

#endif
