#ifndef ABRCC_ABR_INTERFACE_H_
#define ABRCC_ABR_INTERFACE_H_

#include "net/abrcc/service/schema.h"

namespace abr_schema {

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
class AbrInterface {
 public:
  virtual void registerMetrics(const abr_schema::Metrics &) = 0;
  virtual void registerAbort(const int) = 0;
  virtual abr_schema::Decision decide() = 0;
  
  virtual ~AbrInterface();
};

}

#endif
