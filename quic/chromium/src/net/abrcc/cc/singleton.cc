#include "net/abrcc/cc/singleton.h"

#include <filesystem>
#include <iostream>
#include <fstream>
#include <unistd.h>

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wint-to-void-pointer-cast"

/*
 * Dragons be here.
 */

static bool exists(const std::string& name) {
  return ( access( name.c_str(), F_OK ) != -1 );
}

void* SingletonBuilder::GetInstance(const std::string& id, void* instance) {
  int pid = getpid();
  std::string file = "/tmp/tmp_" + std::to_string(pid) + id;
  
  void *location = nullptr;
  if (exists(file)) {
    std::ifstream f(file.c_str());
    f >> location;
  } else {
    location = instance;
    std::ofstream f(file.c_str());
    f << location << '\n';
  }
  return location;
}

SingletonBuilder::SingletonBuilder() {}
SingletonBuilder::~SingletonBuilder() {}

#pragma GCC diagnostic pop
