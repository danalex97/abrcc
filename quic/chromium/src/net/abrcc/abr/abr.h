#ifndef ABRCC_ABR_ABR_H_
#define ABRCC_ABR_ABR_H_

#include "net/abrcc/abr/interface.h"
#include "net/abrcc/service/schema.h"

#include <unordered_map>

namespace quic {

class AbrRandom : public AbrInterface {
 public:
  AbrRandom();
  ~AbrRandom() override;

  void registerMetrics(const abr_schema::Metrics &) override;
  abr_schema::Decision decide() override;
 
 private:
  int last_index;
  int last_timestamp;
  std::unordered_map<int, abr_schema::Decision> decisions; 
};

}

#endif
