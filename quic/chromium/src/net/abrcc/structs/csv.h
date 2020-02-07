#ifndef _STRUCTURED_CSV_H_
#define _STRUCTURED_CSV_H_

#include <unordered_map>
#include <vector>
#include <string>

namespace structs { 

template <typename T>
class CsvReader {
 public:
  CsvReader(const std::string &path);
  virtual ~CsvReader();
 
  T get(const std::string& key, const int line);
 private:
  std::string path;
  
  std::vector<std::string> headers;
  std::unordered_map<std::string, std::vector<T> > values; 
};

}

#endif
