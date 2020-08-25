#include <stdio.h> 
#include <sys/socket.h> 
#include <arpa/inet.h> 
#include <unistd.h> 
#include <string.h> 

#include <random>
#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>
#include <fstream>
#include <iomanip>


const int DEFAULT_PORT = 8080;
const int UPDATE_INTERVAL = 2; 


int main(int argc, char const *argv[]) { 
  int port = DEFAULT_PORT;
  if (argc >= 2) {
    port = std::stoi(argv[1]);
  }

  bool to_log = false;
  std::string log_path = "";
  if (argc >= 3) {
    log_path = argv[2];
    to_log = true;
  }

  int sock = 0, valread = 0; 
  struct sockaddr_in serv_addr; 
  char buffer[1024] = {0}; 
  if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0) { 
      return -1; 
  } 
 
  serv_addr.sin_family = AF_INET; 
  serv_addr.sin_port = htons(port); 
     
  // Convert IPv4 and IPv6 addresses from text to binary form 
  if(inet_pton(AF_INET, "127.0.0.1", &serv_addr.sin_addr)<=0) { 
      return -1; 
  } 

  if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) { 
    return -1; 
  } 

  // Keep reading incoming traffic
  std::ofstream log_stream;
  if (to_log) {
    log_stream.open(log_path);
  }
  auto start = std::chrono::system_clock::now();
  long long total_data = 0;
  while (true) {
    std::string data = "OK"; 
    int sent = send(sock, data.c_str(), data.length(), 0); 
    if (sent < 0) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
      fprintf(stderr, "socket() failed: %s\n", strerror(errno));
    }

    valread = read(sock, buffer, sizeof(buffer)); 
    if (valread >= 0) {
      total_data += valread;
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
      fprintf(stderr, "socket() failed: %s\n", strerror(errno));
    }
      
    auto end = std::chrono::system_clock::now();
    std::chrono::duration<double> elapsed_seconds = end - start;
    if (elapsed_seconds.count() > UPDATE_INTERVAL) {
      double speed = 8. * total_data / elapsed_seconds.count() / 1000. / 1000.;
      std::cout << "Measured speed of " << speed << "mbps\n";

      if (to_log) {
        log_stream << std::fixed << std::setprecision(5) << speed << std::endl << std::flush;
      }

      start = std::chrono::system_clock::now();
      total_data = 0;
    }
  }
  return 0; 
} 
