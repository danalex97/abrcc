#include "net/abrcc/structs/csv.h"

#include <iostream>
#include <fstream>
#include <sstream>

namespace structs {

template <typename T>
CsvReader<T>::CsvReader(const std::string& path) : path(path) {
  std::ifstream stream(this->path);
  std::string line;
  bool first = true;
  while (stream >> line) {
    if (line.size() == 0) {
      continue;
    }

    if (first) {
      first = false;

      // process the headers
      std::istringstream ss(line);
      std::string token;
      while (std::getline(ss, token, ',')) {
        headers.push_back(token);
      }
  
      continue;
    }

    // process usual line
    std::istringstream ss(line);
    std::string token;
    for (int ctr = 0; std::getline(ss, token, ','); ++ctr) {
      auto &key = headers[ctr];
      if (values.find(key) == values.end()) {
        values[key] = std::vector<T>();
      }

      T value;
      std::istringstream raw_value(token);
      raw_value >> value;

      values[key].push_back(value);
    }
 }
}

template <typename T>
CsvReader<T>::~CsvReader() {}

template <typename T>
T CsvReader<T>::get(const std::string& key, const int line){
  return values[key][line];
}

template class CsvReader<long long>;
template class CsvReader<int>;
template class CsvReader<double>;
template class CsvReader<float>;

}
