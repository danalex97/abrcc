from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from socket import *
import requests
import sys
import os
import time
import hashlib
import math
import multiprocessing
from ctypes import c_char_p, c_char
import math
import random
import argparse
import threading
import datetime
import numpy

VIDEO_SERVER_HTTP_PORT = 9000
BUFFER_UPGRADE_LIMIT = 15

class VideoFinished(Exception):
   """Base class for other exceptions"""
   pass

class VideoServer:
    VIDEO_SERVER_HOST = 'localhost'
    PROXY_SERVER_HOST = 'localhost'

    BITRATES = [300, 750, 1200, 1850, 2850, 4300]  # Kbps
    KILO = 1000
    BITS_IN_BYTE = 8
    BUF = 1024  # 1820 # Packet size of 1820 bytes for UDP has the same payload ratio as TCP has
    CHECKSUM_LENGTH = 32  # number of letters the checksum can take up
    CHUNK_NO_LENGTH = 2  # number of digits chunk_no can take up
    SEQ_NO_LENGTH = 6  # number of digits seq_no can take up
    PAYLOAD_SIZE = BUF - CHECKSUM_LENGTH - CHUNK_NO_LENGTH - SEQ_NO_LENGTH

    # Packet pacing parameters to achieve a desired throughput
    PACKET_PACING_MULTIPLIER = 1.5  # In order to make sure that we use all the bandwidth, we send more packets than
    # we theoretically should. The excess packets are temporarily stored in a buffer.
    MSS = 1024 # bytes

    def __init__(self, video_server_port, proxy_server_port, stream_no, log_filename):

        self.video_server_port = video_server_port
        self.proxy_server_port = proxy_server_port
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.bind((self.VIDEO_SERVER_HOST, video_server_port))
        self.proxy_server_addr = (self.PROXY_SERVER_HOST, proxy_server_port)

        self.final_seq_no = 0
        self.lock = multiprocessing.Lock()
        self.is_sending = multiprocessing.Value('i', 0)  # Flag that there is already a process sending data
        self.file_name = multiprocessing.Array('B', 40)
        self.seq_no = multiprocessing.Value('i', 0)
        self.wish_to_change_seq_no = multiprocessing.Value('b', False)  # Flag that shows that seq_no should be changed
        self.new_seq_no = multiprocessing.Value('i', 0)

        # pps: Packet Per Slot (used for packet pacing)
        self.exact_pps = multiprocessing.Value('d', 2)
        self.low_pps = None
        self.high_pps = None
        self.curr_pps = multiprocessing.Value('i', 2)
        self.remainder = None
        self.CWND = multiprocessing.Value('i', random.randint(20,50))  #MSS
        self.SSTHRESHOLD = multiprocessing.Value('i', 64)
        self.estimated_RTT_time = multiprocessing.Value('d', 0)
        self.DevRTT = multiprocessing.Value('d', 0)
        self.timeout_interval = multiprocessing.Value('d', 1)
        self.pace_interval = multiprocessing.Value('d', 0.016)
        self.bitrates = multiprocessing.Array('d', 1000000)
        self.index = multiprocessing.Value('i', 0)
        self.BufferOccupancy = multiprocessing.Array('d', 100)
        self.buf_index = multiprocessing.Value('i', 1)
        self.qualities = multiprocessing.Array('i', 100)
        self.qualities[1] = 4
        self.bw_flag = multiprocessing.Value('d', 0)

        self.log_filename = log_filename
        self.stream_name = 6000 + stream_no
        self.ACKs_arrived = multiprocessing.Value('b', False)
        self.retransmit_req = multiprocessing.Value('b', False)

        self.first_time = multiprocessing.Value('b', True)
        threading.Thread(target=self.listen_to_port).start()

        #second socket for TCP connection to ABR_server
        self.socketTCP = socket(AF_INET, SOCK_STREAM)
        self.socketTCP.bind((self.VIDEO_SERVER_HOST, (VIDEO_SERVER_HTTP_PORT+stream_no)))
        ABR_proc = multiprocessing.Process(target=self.listen_to_ABR)
        ABR_proc.start()

        #ACK history list
        self.last_chunk = multiprocessing.Array('i', stream_no+1)
        self.last_seq = multiprocessing.Array('i', stream_no+1)
        self.lock.acquire()
        for i in range(stream_no+1):
            self.last_chunk[i] = 1
            self.last_seq[i] = -1
        self.lock.release()

        #third socket for ACKs
        self.socketACK = socket(AF_INET, SOCK_DGRAM)
        self.socketACK.bind((self.VIDEO_SERVER_HOST, (video_server_port+50)))
        ACK_proc = multiprocessing.Process(target=self.listen_to_ACK)
        ACK_proc.start()

    def listen_to_ABR(self):
        self.socketTCP.listen(100000)
        conn, addr = self.socketTCP.accept()
        # print('Connected by', addr)
        while True:
            data = conn.recv(1024)
            self.BufferOccupancy[self.buf_index.value] = float(data.split('-')[1])
            self.buf_index.value += 1
            tmp_quality = self.set_quality_rate()
            conn.sendall(str(tmp_quality))
            if self.buf_index.value == 50: # means video is finished (there are 49 chunks in our video)
                raise VideoFinished

    def listen_to_ACK(self):
        while True:
            data, addr = self.socketACK.recvfrom(1024)
            request = data.decode()
            self.stream_name = int(request.split('-')[0])
            chunk_no = int(request.split('-')[1])
            if chunk_no == 0:
                pass
            else:
                seq_no = int(request.split('-')[2])
                last_check = int(request.split('-')[3])
                if self.last_chunk[self.stream_name-6000] == chunk_no \
                    and self.last_seq[self.stream_name-6000] == seq_no-1:
                        if last_check == 1: #last packet in the chunk
                            sys.stdout.write('last\n')
                            self.lock.acquire()
                            self.last_chunk[self.stream_name-6000] = chunk_no + 1
                            self.last_seq[self.stream_name-6000] = -1
                            self.lock.release()
                        else:
                            self.lock.acquire()
                            self.last_chunk[self.stream_name-6000] = int(request.split('-')[1])
                            self.last_seq[self.stream_name-6000] =  int(request.split('-')[2])
                            self.lock.release()

    def listen_to_port(self):
        sending_proc = None
        while True:
            data, addr = self.socket.recvfrom(self.BUF)
            self.lock.acquire()
            request = data.decode()

            file_name = request.split('-')[1]
            seq_no = request.split('-')[3]
            self.file_name = file_name

            if self.is_sending.value == 0:
                self.seq_no.value = int(seq_no)
                sending_proc = multiprocessing.Process(target=self.send_chunk)
                sending_proc.start()
                self.is_sending.value = 1
                self.lock.release()
            else:
                self.wish_to_change_seq_no.value = True
                self.new_seq_no.value = int(seq_no)
                self.lock.release()

    def send_chunk(self):
        # print('\t[' + str(self.proxy_server_port) +'] ' + self.file_name + ' requested')
        self.update_packet_pacing()
        f = open(self.file_name, 'rb')
        start_time = time.time()
        num_pkts_sent = 0
        file_size = os.path.getsize(self.file_name)
        final_seq_no = int(float(file_size) / self.PAYLOAD_SIZE)

        self.lock.acquire()
        if self.wish_to_change_seq_no.value == True:
            # print('\t[' + str(self.proxy_server_port) +'] [Top] wish_to_change_seq_no: ' + str(self.new_seq_no.value))
            self.wish_to_change_seq_no.value = False
            self.seq_no.value = self.new_seq_no.value

        f.seek(self.seq_no.value * self.PAYLOAD_SIZE, 0)
        data = f.read(self.PAYLOAD_SIZE)
        chunk_no = self.get_chunk_no(self.file_name)
        data = (self.stringify(chunk_no, self.CHUNK_NO_LENGTH) + self.stringify(self.seq_no.value,
                                                                                self.SEQ_NO_LENGTH)).encode() + data
        checksum = hashlib.md5(data).hexdigest().encode()
        self.lock.release()

        start_time = time.time()

        while (data and self.seq_no.value < final_seq_no + 1):
            if self.socket.sendto(checksum + data, self.proxy_server_addr):
                num_pkts_sent += 1
                if num_pkts_sent >= self.curr_pps.value:
                    self.check_acks(start_time, seq_no, num_pkts_sent)
                    print(chunk_no)
                    curr_time = time.time()
                    sleep_time = self.pace_interval.value - curr_time + start_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                    
                    start_time = time.time()
                    self.update_packet_pacing()
                    num_pkts_sent = 0

                self.lock.acquire()

                if self.wish_to_change_seq_no.value == True:
                    # print('\t[' + str(self.proxy_server_port) +'] [Bottom] wish_to_change_seq_no: ' + str(self.new_seq_no.value))
                    self.wish_to_change_seq_no.value = False
                    self.seq_no.value = self.new_seq_no.value
                else:
                    self.seq_no.value += 1

                f.seek(self.seq_no.value * self.PAYLOAD_SIZE, 0)
                data = f.read(self.PAYLOAD_SIZE)
                chunk_no = self.get_chunk_no(self.file_name)
                data = (self.stringify(chunk_no, self.CHUNK_NO_LENGTH) + self.stringify(self.seq_no.value,
                                                                                        self.SEQ_NO_LENGTH)).encode() + data
                checksum = hashlib.md5(data).hexdigest().encode()

                seq_no = self.seq_no.value


                self.lock.release()
            else:
                print('\t[' + str(self.proxy_server_port) + '] Error when sending packet')
        self.send_fin_packet()
        f.close()
        self.is_sending.value = 0

    def check_acks(self, start_time, seq_no, num_pkts_sent):
        curr_time = time.time()
        breaked = False

        while curr_time < start_time + self.timeout_interval.value:
            if self.last_seq[self.stream_name-6000] == seq_no:
                self.lock.acquire()
                curr_time = time.time()
                sample_RTT_time = curr_time - start_time
                rate_bps = float(num_pkts_sent) / sample_RTT_time * 1024 * 8

                print(rate_bps)

                self.bitrates[self.index.value] = rate_bps
                self.index.value += 1

                if self.CWND.value < self.SSTHRESHOLD.value:
                    self.CWND.value *= 2
                elif self.CWND.value > random.randint(100,150):
                    self.CWND.value = random.randint(40,80)
                else:
                    self.CWND.value += 1

                self.set_packet_pacing_speed()
                self.pace_interval.value = self.CWND.value * 1024 * 8 * self.PACKET_PACING_MULTIPLIER / self.BITRATES[self.qualities[self.buf_index.value]] / 1000 * 0.93

                breaked = True
                if self.DevRTT.value == 0:
                    self.DevRTT.value = abs(sample_RTT_time - self.estimated_RTT_time.value)
                else:
                    self.DevRTT.value = 0.75 * self.DevRTT.value + 0.25 * abs(sample_RTT_time - self.estimated_RTT_time.value)
                if self.estimated_RTT_time.value == 0:
                    self.estimated_RTT_time.value = sample_RTT_time
                else:
                    self.estimated_RTT_time.value = 0.875 * self.estimated_RTT_time.value + 0.125 * sample_RTT_time

                self.timeout_interval.value = self.estimated_RTT_time.value + 4 * self.DevRTT.value

                stream = self.stream_name - 6000
                time_now = datetime.datetime.now()
                time_str = datetime.time(time_now.hour, time_now.minute, time_now.second, time_now.microsecond)
                file_RTT = self.log_filename + '/RTT_' + str(stream)
                f = open(file_RTT, "a+")
                f.write(str(time_str))
                f.write(" %f" % (sample_RTT_time))
                f.write(" %f" % (self.estimated_RTT_time.value))
                f.write(" %f" % (self.timeout_interval.value))
                f.write(" %f" % (rate_bps))
                f.write(" %f\n" % (self.pace_interval.value))
                self.lock.release()
                break
            curr_time = time.time()

        if breaked == False:
            # print(seq_no)
            # print(self.last_seq[self.stream_name - 6000])
            self.lock.acquire()
            self.retransmit()
            self.SSTHRESHOLD.value = self.CWND.value / 2
            self.CWND.value = self.SSTHRESHOLD.value
            self.timeout_interval.value *= 2
            self.set_packet_pacing_speed()
            self.lock.release()
            print('********************************************************************************************************************\n')
        # else:
        #     time.sleep(0.5)

    def set_quality_rate(self):
        determined_quality = 750
        std = 0
        print(self.BufferOccupancy[self.buf_index.value - 1])
        if self.index.value <= 15 and self.index.value > 2:
            determined_quality = sum(self.bitrates[self.index.value-3:self.index.value-1]) / 2000
        elif self.index.value > 15:
            determined_quality = sum(sorted(self.bitrates[self.index.value-15:self.index.value-1])[0:2]) / 2000

        stream = self.stream_name - 6000
        time_now = datetime.datetime.now()
        time_str = datetime.time(time_now.hour, time_now.minute, time_now.second, time_now.microsecond)
        file_qual = self.log_filename + '/qual_' + str(stream)
        f = open(file_qual, "a+")
        f.write(str(time_str))
        f.write(" %f\n" % (determined_quality))

        print(determined_quality)
        tmp_bitrate = determined_quality

        # find out matching quality level
        tmp_quality = 0
        i = 5
        while i >= 0:
            if tmp_bitrate >= self.BITRATES[i] * 1.1:
                tmp_quality = i
                break
            tmp_quality = i
            i -= 1


        if i < 5:
            # if self.BufferOccupancy[self.buf_index.value - 1] > BUFFER_UPGRADE_LIMIT:
            #     if self.BufferOccupancy[self.buf_index.value - 1] + 4 * determined_quality / self.BITRATES[tmp_quality+1] > 10:
            #         tmp_quality += 1
            if self.qualities[self.buf_index.value-1] > tmp_quality:
                if self.BufferOccupancy[self.buf_index.value - 1] + 4 * determined_quality / self.BITRATES[tmp_quality+1] > 8.5:
                    tmp_quality += 1

        self.pace_interval.value = self.CWND.value * 1024 * 8 * self.PACKET_PACING_MULTIPLIER / self.BITRATES[tmp_quality] / 1000 * 0.93
        self.qualities[self.buf_index.value] = tmp_quality

        if i > 0:
            if self.BufferOccupancy[self.buf_index.value - 1] < 4.5:
                tmp_quality -= 1

        return tmp_quality

    def retransmit(self):
        self.wish_to_change_seq_no.value = True
        self.new_seq_no.value = self.last_seq[self.stream_name-6000] + 1
        self.retransmit_req.value = False
        print('RETRANSMIT')

    def send_fin_packet(self):
        data = 'FIN'.encode()
        file_size = os.path.getsize(self.file_name)
        computed_seq_no = int(math.ceil(file_size / self.PAYLOAD_SIZE) + 1)
        # print('\t[' + str(self.proxy_server_port) + '] Sending FIN packet: ' + str(computed_seq_no) + ' (supposedly from file ' + self.file_name + ')')
        if computed_seq_no != self.seq_no.value:
            raise Exception('[Debug] Final packet has wrong sequence number. This may be due to a bad interleaving.\n' +
                            'computed_seq_no: ' + str(computed_seq_no) + ', seq_no: ' + str(self.seq_no.value))
        chunk_no = self.get_chunk_no(self.file_name)
        data = (self.stringify(chunk_no, self.CHUNK_NO_LENGTH) + self.stringify(computed_seq_no,
                                                                                self.SEQ_NO_LENGTH)).encode() + data
        checksum = hashlib.md5(data).hexdigest().encode()
        self.socket.sendto(checksum + data, self.proxy_server_addr)

    def stringify(self, seq_no, num_digits):
        if seq_no == 0:
            c = 1
        else:
            c = seq_no
        str_seq_no = ''
        limit = math.pow(10, num_digits - 1)
        while c < limit:
            str_seq_no += '0'
            c *= 10
        str_seq_no += str(seq_no)
        return str_seq_no

    # Returns chunk_no given a file path of the form /var/www/html/video6/chunk_no.m4s
    def get_chunk_no(self, file_path):
        file_name = file_path.split('/')[5].split('.')[0]
        if file_name.isdigit():
            return int(file_name)
        elif file_name == 'Header':
            return 0
        else:
            raise Exception('The given file_path does not have the correct format to be parsed into a chunk number')

    def set_packet_pacing_speed(self):
        if self.CWND.value < 1:
            self.CWND.value = 1
        stream = self.stream_name - 6000
        time = datetime.datetime.now()
        time_str = datetime.time(time.hour, time.minute, time.second, time.microsecond)
        file_cwnd = self.log_filename + '/cwnd_' + str(stream)
        f = open(file_cwnd, "a+")
        f.write(str(time_str))
        f.write(" %d\n" % (self.CWND.value))

    def update_packet_pacing(self):
        self.lock.acquire()
        self.exact_pps.value = self.CWND.value * self.MSS / self.BUF
        self.exact_pps.value *= self.PACKET_PACING_MULTIPLIER
        self.low_pps = int(math.floor(self.exact_pps.value))
        self.high_pps = int(math.ceil(self.exact_pps.value))
        self.remainder = 0

        if self.remainder < self.exact_pps.value - self.low_pps:
            self.remainder += self.high_pps - self.exact_pps.value
            self.curr_pps.value = self.high_pps
        else:
            self.remainder -= self.exact_pps.value - self.low_pps
            self.curr_pps.value = self.low_pps
        self.lock.release()

    def close_socket(self):
        self.socket.close()

# define main function to capture interrupts
def main():
    #parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('video_server_port', help='port number from which this proxy server should request the video chunks ', type=int)
    parser.add_argument('proxy_server_port', help='port number on which this proxy server should receive UDP packets from the video server', type=int)
    parser.add_argument('stream_no', type=int)
    parser.add_argument('log_filename', type=str)
    args=parser.parse_args()

    videoServer = VideoServer(args.video_server_port, args.proxy_server_port, args.stream_no, args.log_filename)

if __name__ == "__main__":
    try:
        main()
    except VideoFinished:
        print('Video is finished!')
        os.exit(0)
    except KeyboardInterrupt:
        print("Keyboard interrupted.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

