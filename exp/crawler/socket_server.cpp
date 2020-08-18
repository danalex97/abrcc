#include <unistd.h> 
#include <stdio.h> 
#include <sys/socket.h> 
#include <netinet/in.h> 
#include <string.h> 

#include <string>
#include <random>
#include <algorithm>
#include <chrono>
#include <iostream>

const int DEFAULT_PORT = 8080;
const int BUFFER_SIZE = 1024;
const int UPDATE_INTERVAL = 2; 

std::string random_string(size_t length) {
  auto randchar = []() -> char {
    const char charset[] =
      "0123456789"
      "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
      "abcdefghijklmnopqrstuvwxyz";
    const size_t max_index = sizeof(charset) - 1;
    return charset[rand() % max_index];
  };
  std::string str(length, 0);
  std::generate_n(str.begin(), length, randchar);
  return str;
}


int main(int argc, char const *argv[]) { 
  int server_fd, new_socket, valread; 
  struct sockaddr_in address; 
  int opt = 1; 
  int addrlen = sizeof(address); 
     
  // Creating socket file descriptor 
  if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) { 
      perror("socket failed"); 
      exit(EXIT_FAILURE); 
  } 
     
  // Forcefully attaching socket to the port 8080 
  if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, 
                                                &opt, sizeof(opt)))  { 
      perror("setsockopt"); 
      exit(EXIT_FAILURE); 
  } 
  address.sin_family = AF_INET; 
  address.sin_addr.s_addr = INADDR_ANY; 
  address.sin_port = htons(DEFAULT_PORT); 
     
  // Forcefully attaching socket to the port 8080 
  if (bind(server_fd, (struct sockaddr *)&address,  
                               sizeof(address))<0) { 
      perror("bind failed"); 
      exit(EXIT_FAILURE); 
  }
  if (listen(server_fd, 3) < 0) { 
      perror("listen"); 
      exit(EXIT_FAILURE); 
  } 
  if ((new_socket = accept(server_fd, (struct sockaddr *)&address,  
                     (socklen_t*)&addrlen))<0) { 
      perror("accept"); 
      exit(EXIT_FAILURE); 
  } 

  // keep sending traffic
  auto start = std::chrono::system_clock::now();
  double total_data = 0;
  while (true) {
    std::string data = random_string(BUFFER_SIZE); 

    send(new_socket, data.c_str(), data.length() + 1, 1); 
    total_data += data.length();
    
    auto end = std::chrono::system_clock::now();
    std::chrono::duration<double> elapsed_seconds = end - start;
    if (elapsed_seconds.count() > UPDATE_INTERVAL) {
      double speed = 8. * total_data / elapsed_seconds.count() / 1000. / 1000.;

      start = std::chrono::system_clock::now();
      total_data = 0;
    }
  }
} 

