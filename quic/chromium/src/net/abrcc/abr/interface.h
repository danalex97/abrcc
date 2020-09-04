#ifndef ABRCC_ABR_INTERFACE_H_
#define ABRCC_ABR_INTERFACE_H_

#include "net/abrcc/service/schema.h"

namespace abr_schema {

// Decision for the `quality` of segment with `index`, `timestamp`-ed by the latest 
// front-end metric's timestamp. The front-end will take into account the decision with
// the largest `timestamp` for a particular segment `index`.
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
  std::string path();
  std::string resourcePath();
  std::string videoPath();

  // noop decision -- to integrate Minerva
  bool noop();
};

}

namespace quic {

// AbrInterface. Implement the methods:
//  - registerMetrics: react to new front-end metrics
//  - registerAbort: update internal state after an abort request at a given segment index
//  - decide: return a decision for quality of the next(according to the metrics) segment 

class AbrInterface {
 public:
  virtual void registerMetrics(const abr_schema::Metrics &) = 0;
  virtual void registerAbort(const int) = 0;
  virtual abr_schema::Decision decide() = 0;
  
  virtual ~AbrInterface();
};

}

#endif
