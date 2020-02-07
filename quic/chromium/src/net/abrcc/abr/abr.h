#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

#include "net/abrcc/dash_config.h"

#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/bbr_adapter.h"
#include "net/abrcc/service/schema.h"

#include "net/abrcc/structs/averages.h"
#include "net/abrcc/structs/csv.h"

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

class WorthedAbr : public SegmentProgressAbr {
 public:
  WorthedAbr();
  ~WorthedAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;
 private:
  int adjustedBufferLevel(int index);
  
  std::pair<int, int> computeRates(bool stochastic);
  void adjustCC(); 
  void setRttProbing(bool probing);

  int ban;
  BbrAdapter::BbrInterface* interface; 

  bool is_rtt_probing;

  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
  std::unique_ptr<structs::MovingAverage<double>> average_bandwidth;  

  base::Optional<abr_schema::Value> last_bandwidth;
  base::Optional<abr_schema::Value> last_rtt;
};

class TargetAbr : public SegmentProgressAbr {
 public:
  TargetAbr(const std::string& video_info_path);
  ~TargetAbr() override;
 
  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;  
 private:
  structs::CsvReader<double> video_info;

  int vmaf(const int quality, const int index);
};

AbrInterface* getAbr(const std::string& abr_type, const std::shared_ptr<DashBackendConfig>& config);

}

#pragma GCC diagnostic pop


#endif
