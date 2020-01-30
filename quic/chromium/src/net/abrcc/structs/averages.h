#ifndef _STRUCTURES_AVERAGES_H_
#define _STRUCTURES_AVERAGES_H_

#include <queue>

namespace structs { 

template <typename T>
class MovingAverage {
 public:
  MovingAverage(int size); 
  virtual ~MovingAverage();

  void sample(T sample);
  bool empty() const;
  int size() const;
  T last() const;

  double value_or(double _default) const;
  virtual double value() const = 0;
 
 protected:
  virtual void push(T sample) = 0;
  virtual void pop(T sample) = 0;

 private:
  int _size;
  std::deque<T> samples;
};

template <typename T>
class SimpleMovingAverage : public MovingAverage<T> {
 public:
  SimpleMovingAverage(int size);
  double value() const override;
 
 private:
  void push(T sample) override;
  void pop(T sample) override;

  double total;
};


template <typename T>
class WilderEMA : public MovingAverage<T> {
 public:
  WilderEMA(int size);
  double value() const override;
 
 private:
  void push(T sample) override;
  void pop(T sample) override;

  double m;
  double ema;
};

}

#endif
