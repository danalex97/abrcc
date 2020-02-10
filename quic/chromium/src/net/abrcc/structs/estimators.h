#ifndef _STRUCTURES_ESTIMATORS_H_
#define _STRUCTURES_ESTIMATORS_H_

#include "net/abrcc/structs/averages.h"

#include <set>
#include <map>
#include <queue>

namespace structs {

template <typename T>
class PIDEstimator : public MovingAverage<T> {
 public:
  PIDEstimator(int size, float p, float i, float d);
  double value() const override;
 
 private:
  double proportional() const;
  double integral() const;
  double derivative() const;

  void push(T sample) override;
  void pop(T sample) override;
  
  float p, i, d;
  double total, last;
  int ctr;

  std::multiset<double> st;
  std::map<double, int> pos;
};


template <typename T>
class LineFitEstimator : public MovingAverage<T> {
 public:
  LineFitEstimator(int size, T time_delta, int projection_size);
  double value() const override;
 
 private:
  void push(T sample) override;
  void pop(T sample) override;

  int projection_size;
  double time_delta;
  double last_time;
  std::deque<std::pair<double, double> > points;
  std::unique_ptr<MovingAverage<double> > final_point_estimate;  

  double lsm_slope() const;
};


}

#endif
