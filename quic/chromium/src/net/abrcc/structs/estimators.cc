#include "net/abrcc/structs/estimators.h"

#include <iostream>

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

namespace structs {

template <typename T>
PIDEstimator<T>::PIDEstimator(int size, float p, float i, float d) 
  : MovingAverage<T>(size)
  , p(p), i(i), d(d)
  , total(0)
  , ctr(0)
  , st(std::multiset<double>{}) 
  , pos(std::map<double, int>{}){}

template <typename T>
void PIDEstimator<T>::push(T value) {
  last = value;
  total += value;
  
  st.insert(static_cast<double>(value));
  pos[value] = ++ctr;
}

template <typename T>
void PIDEstimator<T>::pop(T value) {
  total -= value;
  st.erase(st.find(static_cast<double>(value)));
}

template <typename T>
double PIDEstimator<T>::value() const {
  return (
    1. * p * proportional() + 
    1. * i * integral() + 
    1. * d * derivative()
  ) / (p + i + d);
}

template <typename T>
double PIDEstimator<T>::proportional() const {
  return last;
}

template <typename T>
double PIDEstimator<T>::integral() const {
  return total / this->size();
}

template <typename T>
double PIDEstimator<T>::derivative() const {
  double mx = *(st.rbegin());
  double mn = *(st.begin());
  return pos.find(mx)->second > pos.find(mn)->second ? mx - mn : mn - mx;
}


template class PIDEstimator<long long>;
template class PIDEstimator<int>;
template class PIDEstimator<double>;
template class PIDEstimator<float>;


template <typename T>
LineFitEstimator<T>::LineFitEstimator(int size, T time_delta, int projection_size) 
  : MovingAverage<T>(size)
  , projection_size(projection_size)
  , time_delta(static_cast<double>(time_delta))
  , last_time(0)
  , points(std::deque<std::pair<double, double>>{})
  , final_point_estimate(new WilderEMA<double>(size)) 
  { }

template <typename T>
void LineFitEstimator<T>::push(T value) {
  points.push_back(std::make_pair(static_cast<double>(value), last_time)); 
  
  final_point_estimate->sample(value);
  last_time += time_delta; 
}

template <typename T>
void LineFitEstimator<T>::pop(T value) {
  points.pop_front();
}

template <typename T>
double LineFitEstimator<T>::value() const {
  if (int(points.size()) != this->size()) {
    return final_point_estimate->value();
  }
  
  double m = lsm_slope();
  double future_dist = time_delta * projection_size;

  return final_point_estimate->value() + future_dist * m; 
}

template <typename T> 
double LineFitEstimator<T>::lsm_slope() const {
  double avg_x = 0;
  double avg_y = 0;
  for (auto &[x, y] : points) {
    avg_x += x;
    avg_y += y;
  }
  avg_x /= points.size();
  avg_y /= points.size();

  double num = 0;
  double den = 0;
  for (auto &[x, y] : points) {
    num += (x - avg_x) * (y - avg_y);  
    den += (x - avg_x) * (x - avg_x);
  }
  return num / den;
}


template class LineFitEstimator<long long>;
template class LineFitEstimator<int>;
template class LineFitEstimator<double>;
template class LineFitEstimator<float>;

}

#pragma GCC diagnostic pop
