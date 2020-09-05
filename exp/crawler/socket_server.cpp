#include <unistd.h> 
#include <stdio.h> 
#include <sys/socket.h> 
#include <netinet/in.h> 
#include <string.h> 
#include <errno.h>

#include <string>
#include <random>
#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>
#include <fstream>
#include <iomanip>

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
  // Single flow TCP client that keeps sending data.
  int server_fd, new_socket, valread; 
  struct sockaddr_in address; 
  int opt = 1; 
  char buffer[1024] = {0}; 
  int addrlen = sizeof(address); 

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
  address.sin_port = htons(port); 
     
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

  std::ofstream log_stream;
  if (to_log) {
    log_stream.open(log_path);
  }

  // keep sending traffic
  auto start = std::chrono::system_clock::now();
  double total_data = 0;
  while (true) {
    int valread = read(new_socket, buffer, 1024); 
    if (valread < 0) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
      fprintf(stderr, "socket() failed: %s\n", strerror(errno));
    }
    std::string data = random_string(BUFFER_SIZE - 5); 

    int sent = send(new_socket, data.c_str(), data.length(), MSG_NOSIGNAL | MSG_DONTWAIT); 
    if (sent < 0) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
      fprintf(stderr, "socket() failed: %s\n", strerror(errno));
    }
    total_data += data.length();
    
    auto end = std::chrono::system_clock::now();
    std::chrono::duration<double> elapsed_seconds = end - start;
    if (elapsed_seconds.count() > UPDATE_INTERVAL) {
      double speed = 8. * total_data / elapsed_seconds.count() / 1000. / 1000.;
      //std::cout << "Measured speed of " << speed << "mbps\n";
 
      //if (to_log) {
      //  log_stream << std::fixed << std::setprecision(5) << speed << std::endl;
      //}

      start = std::chrono::system_clock::now();
      total_data = 0;
    }
  }
} 

