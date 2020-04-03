#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

#include "net/abrcc/dash_config.h"

#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/bbr_adapter.h"
#include "net/abrcc/cc/target.h"
#include "net/abrcc/service/schema.h"

#include "net/abrcc/structs/averages.h"

#include <unordered_map>

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

class StateTracker {
 public:
  StateTracker();
  virtual ~StateTracker();

  void registerMetrics(const abr_schema::Metrics &);
 protected:
  BbrAdapter::BbrInterface* interface; 

  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
  std::unique_ptr<structs::MovingAverage<double>> average_bandwidth;  

  base::Optional<abr_schema::Value> last_bandwidth;
  base::Optional<abr_schema::Value> last_rtt;
 private:
  int last_timestamp;
};

class WorthedAbr : public SegmentProgressAbr, public StateTracker {
 public:
  WorthedAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~WorthedAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;
 private:
  int adjustedBufferLevel(int index);
  
  std::pair<int, int> computeRates(bool stochastic);
  void adjustCC(); 
  void setRttProbing(bool probing);

  int ban;
  bool is_rtt_probing;
};

class TargetAbr : public SegmentProgressAbr, public StateTracker {
 public:
  TargetAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~TargetAbr() override;
 
  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;  
 private:
  int vmaf(const int quality, const int index);
  std::pair<double, int> qoe(const double bandwidth);

  void adjustCC();

  std::unique_ptr<structs::MovingAverage<double>> bw_estimator;  

  int bandwidth_target;
  int last_adjustment_bandwidth;
};

class TargetAbr2 : public SegmentProgressAbr {
 public:
  TargetAbr2(const std::shared_ptr<DashBackendConfig>& config);
  ~TargetAbr2() override;
 
  void registerMetrics(const abr_schema::Metrics &) override;
  int decideQuality(int index) override;  
 private:
  int vmaf(const int quality, const int index);
  std::pair<double, int> qoe(const double bandwidth);

  void adjustCC();

  std::unique_ptr<structs::MovingAverage<double>> bw_estimator;  

  int bandwidth_target;
  
  // StateTracker state
  BbrTarget::BbrInterface* interface; 

  abr_schema::Value last_player_time;
  abr_schema::Value last_buffer_level;
  std::unique_ptr<structs::MovingAverage<double>> average_bandwidth;  

  base::Optional<abr_schema::Value> last_bandwidth;
  base::Optional<abr_schema::Value> last_rtt;
  int last_timestamp;
};

AbrInterface* getAbr(
  const std::string& abr_type, 
  const std::shared_ptr<DashBackendConfig>& config
);

}

#pragma GCC diagnostic pop


#endif
