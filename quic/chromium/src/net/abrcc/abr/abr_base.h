#ifndef ABRCC_ABR_ABR_BASE_H_
#define ABRCC_ABR_ABR_BASE_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

// data structure deps
#include "net/abrcc/dash_config.h"

#include <unordered_map>
#include <unordered_set>
#include <vector>

// interfaces
#include "net/abrcc/abr/interface.h"
#include "net/abrcc/cc/bbr_adapter.h"


namespace quic {

// SegmentProgressAbr is a class that downloads the segments one after the other 
// and makes the decision for the next segment when the download of a segments is at 80\%,
// allowing for continous streaming.
//
// To use the SegmentProcessAbr class, only the `decideQuality` function needs to be 
// implemented: it asks for the quality for segment `decision_index`.
// 
// The protected members can be used by class that inherit from SegmentProgressAbr:
//   - last_segment: map that contains the lastest timestamped segment information for each 
//                   downloaded(or started download) segment
//   - decisions: map of previous Decisions
//   - aborted: mpa of previous aborted segments 
//   
//   - decision_index: current segment that needs a Decision
//   - last_timestamp: the highest timestamp for any received Segment 
//   - last_segment_time_length: the previous segment's time length in milliseconds
// 
//   - segments: metadata structure for the whole video(a vector of VideoInfo per track)
//   - bitrate_array: the list of qualities(in kbps) in increasing order
class SegmentProgressAbr : public AbrInterface {
 public:
  SegmentProgressAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~SegmentProgressAbr() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  void registerAbort(const int) override;
  abr_schema::Decision decide() override;

  virtual int decideQuality(int index) = 0; 
 protected:
  const std::shared_ptr<DashBackendConfig>& config;
  std::unordered_map<int, abr_schema::Segment> last_segment;  
  std::unordered_map<int, abr_schema::Decision> decisions; 
  std::unordered_set<int> aborted;

  int decision_index;
  int last_timestamp;
  int last_segment_time_length;

  std::vector< std::vector<VideoInfo> > segments;
  std::vector<int> bitrate_array;
 private:
  void update_segment(abr_schema::Segment segment);
  bool should_send(int index);
};

// Example class that inherits from RandomAbr and selects random segments.
class RandomAbr : public SegmentProgressAbr {
 public: 
  RandomAbr(const std::shared_ptr<DashBackendConfig>& config);
  ~RandomAbr() override;

 int decideQuality(int index) override;
};

// Example class that inherits from RandomAbr and implements a simple sever-side 
// buffer-based policy. It should do identical decisions with the Typescript equivalent
// class from the DASH wrapper project.
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
