#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#include "net/abrcc/abr/schema.h"

namespace quic {

class AbrInterface {
 public:
  virtual void registerMetrics(const abr_schema::Metrics &) = 0;
  virtual abr_schema::Decision decide() = 0;
  
  virtual ~AbrInterface();
};

class AbrRandom : public AbrInterface {
 public:
  AbrRandom();
  ~AbrRandom() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  abr_schema::Decision decide() override;
};

}

#endif
