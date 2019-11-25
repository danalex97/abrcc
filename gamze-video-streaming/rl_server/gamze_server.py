#!/usr/bin/env python
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from socket import *
import SocketServer
import base64
import urllib
import requests
import httplib
import sys
import os
import logging
import json
import random
import multiprocessing
import threading

from collections import deque
import numpy as np
import time
from time import sleep
import datetime

VIDEO_BIT_RATE = [300, 750, 1200, 1850, 2850, 4300]  # Kbps
BITRATE_REWARD = [1, 2, 3, 12, 15, 20]
BITRATE_REWARD_MAP = {0: 0, 300: 1, 750: 2, 1200: 3, 1850: 12, 2850: 15, 4300: 20}
M_IN_K = 1000.0
DEFAULT_QUALITY = 0  # default video quality without agent
REBUF_PENALTY = 4.3  # 1 sec rebuffering -> this number of Mbps
SMOOTH_PENALTY = 1
TOTAL_VIDEO_CHUNKS = 48
SUMMARY_DIR = './results'
LOG_FILE = './results/log'
chunk_no = 0
port_no = None
server_no = 0  # for debugging purposes only
# in format of time_stamp bit_rate buffer_size rebuffer_time video_chunk_size download_time reward

CUSHION = 10

VIDEO_SERVER_HTTP_PORT = 9000
VIDEO_SERVER_HTTP_ADDR = 'localhost'
ABR_SERVER_QUALITY_PORT = 10000


def inform_video_server(chunk_no, buffer_occupancy):
    data = 'buffer_occupancy-' + str(buffer_occupancy)
    socketTCP.send(data.encode())
    data = socketTCP.recv(1024)
    tmp_quality = int(data)
    return tmp_quality


def inform_video_server_init(port):
    global socketTCP
    socketTCP = socket(AF_INET, SOCK_STREAM)
    socketTCP.bind((VIDEO_SERVER_HTTP_ADDR, port+4000))
    socketTCP.connect((VIDEO_SERVER_HTTP_ADDR, port+3000))

def make_request_handler(input_dict):
    global server_no
    server_no += 1
    local_server_no = server_no

    class Request_Handler(BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self.connection_control = 0
            self.input_dict = input_dict
            self.log_file = input_dict['log_file']
            BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

            # os.system('iperf -s') # testing bandwidth

        def do_POST(self):
            # print >>  sys.stderr, 'here'
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))
            send_data = ''

            if 'lastquality' in post_data:
                start_time = datetime.datetime.now()
                global chunk_no
                chunk_no += 1
                rebuffer_time = float(post_data['RebufferTime'] - self.input_dict['last_total_rebuf'])
                reward = \
                    VIDEO_BIT_RATE[post_data['lastquality']] / M_IN_K \
                    - REBUF_PENALTY * (post_data['RebufferTime'] - self.input_dict['last_total_rebuf']) / M_IN_K \
                    - SMOOTH_PENALTY * np.abs(VIDEO_BIT_RATE[post_data['lastquality']] -
                                              self.input_dict['last_bit_rate']) / M_IN_K
                # reward = BITRATE_REWARD[post_data['lastquality']] \
                #         - 8 * rebuffer_time / M_IN_K - np.abs(BITRATE_REWARD[post_data['lastquality']] - BITRATE_REWARD_MAP[self.input_dict['last_bit_rate']])

                video_chunk_fetch_time = post_data['lastChunkFinishTime'] - post_data['lastChunkStartTime']
                if video_chunk_fetch_time == 0:
                    video_chunk_fetch_time = 0.9
                video_chunk_size = post_data['lastChunkSize']
                time = datetime.datetime.now()
                time_str = datetime.time(time.hour, time.minute, time.second, time.microsecond)
                # log wall_time, bit_rate, buffer_size, rebuffer_time, video_chunk_size, download_time, reward
                self.log_file.write(str(time_str) + '\t' +
                                    str(VIDEO_BIT_RATE[post_data['lastquality']]) + '\t' +
                                    str(post_data['buffer']) + '\t' +
                                    str(float(post_data['RebufferTime'] - self.input_dict[
                                        'last_total_rebuf']) / M_IN_K) + '\t' +
                                    str(video_chunk_size) + '\t' +
                                    str(video_chunk_fetch_time) + '\t' +
                                    str(reward) + '\n')
                self.log_file.flush()

                self.input_dict['last_total_rebuf'] = post_data['RebufferTime']
                self.input_dict['last_bit_rate'] = VIDEO_BIT_RATE[post_data['lastquality']]

                if (post_data['lastRequest'] == TOTAL_VIDEO_CHUNKS):
                    send_data = ''  # send_data = "REFRESH" we don't want the video to restart
                    self.input_dict['last_total_rebuf'] = 0
                    self.input_dict['last_bit_rate'] = DEFAULT_QUALITY
                    self.log_file.write('\n')  # so that in the log we know where video ends
                    print("done_successful")  # signal player finished a video
                    sys.stdout.flush()

            # p = multiprocessing.Process(target=inform_video_server, args=(chunk_no, post_data['buffer']))
            # p.start()

            tmp_quality = inform_video_server(chunk_no, post_data['buffer'])
            print('returned++++++++++++++++++++++')

            send_data = str(tmp_quality)

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(send_data))
            self.send_header('Access-Control-Allow-Origin', "*")
            self.end_headers()
            self.wfile.write(send_data)


        def do_GET(self):
            # print >> sys.stderr, 'GOT REQ'
            self.send_header('Cache-Control', 'max-age=3000')
            self.send_header('Content-Length', 20)
            self.end_headers()
            self.wfile.write("console.log('here');")

        def log_message(self, format, *args):
            return

    return Request_Handler


def shutdown(server):
    server.shutdown()
    print("done_successful")  # signal player finished a video
    print >> sys.stderr, 'shutdown complete'


def run(port, log_file_path, time_to_run):
    sys.stdout.write('Listening on port ' + str(port))
    if not os.path.exists(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)

    with open(log_file_path, 'wb') as log_file:
        last_bit_rate = DEFAULT_QUALITY
        last_total_rebuf = 0
        input_dict = {'log_file': log_file,
                      'last_bit_rate': last_bit_rate,
                      'last_total_rebuf': last_total_rebuf}

        handler_class = make_request_handler(input_dict=input_dict)
        server_address = ('localhost', port)
        httpd = HTTPServer(server_address, handler_class)

        print 'Listening on port ' + str(port)
        global port_no
        port_no = port
        sys.stdout.flush()

        t = threading.Timer(interval=time_to_run, function=shutdown, args=httpd)
        t.start()
        # print >>  sys.stderr, 'Listening on port ', str(port)
        httpd.serve_forever()


def main():
    if len(sys.argv) == 4:
        port = int(sys.argv[1])
        inform_video_server_init(port)
        trace_file = sys.argv[2]
        time_to_run = int(sys.argv[3])
        run(port=port, log_file_path=trace_file, time_to_run=time_to_run)
        sys.stdout.write('Listening on port ' + str(port))
    else:
        run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.debug("Keyboard interrupted.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
