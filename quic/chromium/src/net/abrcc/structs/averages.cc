#include "net/abrcc/structs/averages.h"

namespace structs {

template <typename T>
MovingAverage<T>::MovingAverage(int size) 
  : _size(size)
  , samples(std::deque<T>()) {}

template <typename T>
MovingAverage<T>::~MovingAverage() {}

template <typename T>
void MovingAverage<T>::sample(T sample) {
  if (int(samples.size()) == _size) {
    pop(samples.front());
    samples.pop_front();
  }
  samples.push_back(sample);
  push(sample);
} 

template <typename T>
T MovingAverage<T>::last() const {
  return samples.back(); 
}

template <typename T>
bool MovingAverage<T>::empty() const {
  return samples.empty(); 
}

template <typename T>
int MovingAverage<T>::size() const {
  return samples.size(); 
}

template <typename T>
double MovingAverage<T>::value_or(double _default) const {
  if (empty()) {
    return _default;
  }
  return value(); 
}

template class MovingAverage<long long>;
template class MovingAverage<int>;
template class MovingAverage<double>;
template class MovingAverage<float>;


template <typename T>
SimpleMovingAverage<T>::SimpleMovingAverage(int size) 
  : MovingAverage<T>(size)
  , total(0) {}

template <typename T>
void SimpleMovingAverage<T>::push(T value) {
  total += value;
}

template <typename T>
void SimpleMovingAverage<T>::pop(T value) {
  total -= value;
}

template <typename T>
double SimpleMovingAverage<T>::value() const {
  return total / this->size(); 
}

template class SimpleMovingAverage<long long>;
template class SimpleMovingAverage<int>;
template class SimpleMovingAverage<double>;
template class SimpleMovingAverage<float>;


template <typename T>
WilderEMA<T>::WilderEMA(int size) 
  : MovingAverage<T>(size)
  , m(1. / double(size))
  , ema(0) {}

template <typename T>
void WilderEMA<T>::push(T value) {
  ema = m * value + (1 - m) * ema;
}

template <typename T>
void WilderEMA<T>::pop(T value) {
}

template <typename T>
double WilderEMA<T>::value() const {
  return ema; 
}

template class WilderEMA<long long>;
template class WilderEMA<int>;
template class WilderEMA<double>;
template class WilderEMA<float>;


}
