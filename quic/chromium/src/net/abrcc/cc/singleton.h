#pragma once

#ifndef ABRCC_CC_SINGLETON_H_
#define ABRCC_CC_SINGLETON_H_

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wc++17-extensions"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wexit-time-destructors"

#include <map>
#include <string>

/*
 * Per-process and per-class singleton.
 */

#define GET_SINGLETON(type) \
  (reinterpret_cast<type*>( SingletonBuilder::GetInstance(#type, new type()) ))

class SingletonBuilder {
 public: 
  static void* GetInstance(const std::string& id, void* instance); 
  
  SingletonBuilder(const SingletonBuilder&) = delete;
  SingletonBuilder& operator= (const SingletonBuilder) = delete;

 protected:
  SingletonBuilder();
  virtual ~SingletonBuilder();
};

#pragma GCC diagnostic pop
#pragma GCC diagnostic pop

#endif
