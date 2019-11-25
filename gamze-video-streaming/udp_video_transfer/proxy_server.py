from http.server import BaseHTTPRequestHandler, HTTPServer
from socket import *
import sys
import select
import os
import logging
import hashlib
import time
import argparse


num_retransmissions = 0 # for statistical purposes only

def make_request_handler(proxy_server_port, video_server_port, dir_name):
    class ProxyServer(BaseHTTPRequestHandler):

        PROXY_SERVER_HOST = 'localhost'
        VIDEO_SERVER_HOST = 'localhost'
        BASE_PATH = '/var/www/html'
        BUF = 1024 #1820
        CHECKSUM_LENGTH = 32 # number of letters the checksum can take up
        CHUNK_NO_LENGTH = 2 # number of digits chunk_no can take up
        SEQ_NO_LENGTH = 6 # number of digits seq_no can take up


        def __init__(self, *args, **kwargs):
            self.proxy_server_port = proxy_server_port
            self.video_server_port = video_server_port  
            self.socket = socket(AF_INET,SOCK_DGRAM)
            self.socket.bind((self.PROXY_SERVER_HOST, proxy_server_port))
            self.video_server_addr = (self.VIDEO_SERVER_HOST, video_server_port)
            self.socketACK = socket(AF_INET,SOCK_DGRAM)
            self.socketACK.bind((self.PROXY_SERVER_HOST, (proxy_server_port+50)))
            self.video_serverACK_addr = (self.VIDEO_SERVER_HOST, (video_server_port + 50))
            self.file_requests = []
            self.last_check = 1
            BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/m4s')
            self.send_header('Content-Disposition', 'attachment; file_name="Header.m4s"')
            self.end_headers()
            self.stream_name = self.headers.get('Referer').split('=')[1]

            #print(self.headers)
            #print(self.client_address)            
            #print('[' + self.stream_name + '] Requesting ' + self.path)

            file_name = self.BASE_PATH + self.path
            self.file_requests.append(file_name)

            temp_file_name = self.get_udp_chunk(file_name)
            self.send_tcp_chunk(temp_file_name)

        def get_udp_chunk(self, file_name):
            self.last_check = 0
            global num_retransmissions
            start_time = time.time()
            retransmission_seq_no = -1
            num_backoff_pkts_required = 10
            num_backoff_pkts = num_backoff_pkts_required
            request = 'Request: Transmission\nFile-' + file_name + '-\nseq_no-0-'
            data = ''.encode()
            timeout_happened = False

            self.socket.sendto(request.encode(), self.video_server_addr)
            data, addr = self.socket.recvfrom(self.BUF)
            # self.socket.settimeout(0.1) #was 0.1
            # success = False
            # while not success:
            #     try:
            #         success = True
            #         self.socket.sendto(request.encode(), self.video_server_addr)
            #         data, addr = self.socket.recvfrom(self.BUF)
            #     except timeout:
            #         success = False
                
            temp_file_name = dir_name + '/' + file_name.split('/')[4] + '/' + file_name.split('/')[5]            
            f = open(temp_file_name, 'wb')
            prev_seq_no = -1
                        
            temp_file_name = dir_name + '/' + file_name.split('/')[4] + '/' + file_name.split('/')[5]            
            f = open(temp_file_name, 'wb')
            
            while True:
                # sys.stdout.write('Retrans:  ')
                # sys.stdout.write(str(num_retransmissions))
                # print('.')
                # If a timeout occured during the last iteration of the loop, we don't look at any data. Instead we wait for the next packet.  
                if timeout_happened:
                    timeout_happened = False
                else:                                
                    received_checksum = data[:self.CHECKSUM_LENGTH].decode()
                    computed_checksum = hashlib.md5(data[self.CHECKSUM_LENGTH:]).hexdigest()
                    if received_checksum == computed_checksum:
                        received_chunk_no = self.to_int(data[self.CHECKSUM_LENGTH: self.CHECKSUM_LENGTH + self.CHUNK_NO_LENGTH].decode(), self.CHUNK_NO_LENGTH)
                        received_seq_no = self.to_int(data[self.CHECKSUM_LENGTH + self.CHUNK_NO_LENGTH :self.CHECKSUM_LENGTH  + self.CHUNK_NO_LENGTH + self.SEQ_NO_LENGTH].decode(), self.SEQ_NO_LENGTH)
                        chunk_no = self.get_chunk_no()
                        if received_chunk_no == chunk_no:
                            if received_seq_no == prev_seq_no + 1:
                                prev_seq_no += 1
                                num_backoff_pkts = num_backoff_pkts_required
                                payload = data[self.CHECKSUM_LENGTH + self.CHUNK_NO_LENGTH + self.SEQ_NO_LENGTH:]
                                if payload == 'FIN'.encode():
                                    self.last_check = 1
                                    self.send_ack(1, received_chunk_no, received_seq_no)
                                    break
                                f.write(payload)
                                self.last_check = 0
                                self.send_ack(0, received_chunk_no, received_seq_no)
                            elif received_seq_no < prev_seq_no + 1:
                                payload = data[self.CHECKSUM_LENGTH + self.CHUNK_NO_LENGTH + self.SEQ_NO_LENGTH:]
                                if payload != 'FIN'.encode():
                                    self.last_check = 0
                                    self.send_ack(0, received_chunk_no, received_seq_no)
                                                          
                data, addr = self.socket.recvfrom(self.BUF)
                           
            self.socket.close()
            f.close()
            return temp_file_name    
            
        def send_tcp_chunk(self, temp_file_name):
            received_chunk_size = os.path.getsize(temp_file_name)
            split_file_name = temp_file_name.split('/')
            file_name_suffix = split_file_name[2] + '/' + split_file_name[3]
            original_chunk_size = os.path.getsize(self.BASE_PATH  + '/' + file_name_suffix)
            
            if received_chunk_size != original_chunk_size:
                raise Exception('[' + self.stream_name + '] UDP packets were lost. File \'' + file_name_suffix + '\' was not downloaded properly. ' +
                 'Consider lowering the packet pacing rate at the UDP video server. Alternatively, you can change the packet ' +
                 'pacing to be more fine-grained. The size of the received chunk is ' + str(received_chunk_size) + ' bytes,  whereas ' +
                 'the real size of the chunk is ' + str(original_chunk_size) + ' bytes.') 
                                 
            with open(temp_file_name, 'rb') as file:
                self.wfile.write(file.read()) # Read the file and send the content
                
            self.file_requests.pop()
            os.remove(temp_file_name)
                         
        def to_int(self, str_no, str_len):
            for i in range(str_len):
                if str_no[i] != '0':
                    break
            no = int(str_no[i:])
                
            return no
        
        # Returns chunk_no that is currently at the front of the file_requests queue
        def get_chunk_no(self):
            file_path = self.file_requests[0]
            file_name = file_path.split('/')[5].split('.')[0]
            if file_name.isdigit():
                return int(file_name)
            elif file_name == 'Header':
                return 0
            else:
                raise Exception('The given file_path does not have the correct format to be parsed into a chunk number')
                     
        # The following function surpresses the default output from BaseHTTPRequestHandler
        def log_message(self, format, *args):
            return

        def send_ack(self, last_check, received_chunk_no, received_seq_no):
            ack_data = str(self.stream_name) + "-" + str(received_chunk_no) + "-" + str(received_seq_no) + "-" + str(last_check)
            self.socketACK.sendto(ack_data.encode(), self.video_serverACK_addr)


    return ProxyServer
    

def init(args):
    dir_name = 'udp_video_transfer/proxy_temp_chunks_' + str(args.video_server_udp_port)

    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

    for i in range(1, 7):
        sub_dir_name = dir_name + '/video' + str(i)
        if not os.path.exists(sub_dir_name):
            os.makedirs(sub_dir_name)
    
    handler_class = make_request_handler(args.proxy_server_udp_port, args.video_server_udp_port, dir_name)
    proxyServer = HTTPServer(('parallels-Parallels-Virtual-Platform', args.proxy_server_http_port), handler_class)

    proxyServer.serve_forever()
    proxyServer.server_close()       
        

# define main function to capture interrupts
def main():
    #parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('proxy_server_http_port', help='port number which this proxy server should receive HTTP requests on', type=int)
    parser.add_argument('proxy_server_udp_port', help='port number on which this proxy server should receive UDP packets from the video server', type=int)
    parser.add_argument('video_server_udp_port', help='port number from which this proxy server should request the video chunks ', type=int)
    args=parser.parse_args()

    sys.stdout.write("PROXY\n")

    init(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupted.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

