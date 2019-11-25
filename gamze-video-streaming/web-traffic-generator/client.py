from socket import *
import time
import random
import sys
import os
import argparse


# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('filename', help='file that downloading times are written', type=str)
parser.add_argument('website', help='which website the client wants', type=str)

global args
args = parser.parse_args()

BASE_PATH = '/var/www/html/websites'
socketClient = socket(AF_INET, SOCK_STREAM)
socketClient.connect(('localhost', 5600))
request = BASE_PATH + '/' + args.website + '.html'
print(request)
start_time = time.time()
socketClient.send(request.encode())
while True:
	data = socketClient.recvfrom(1024)
	# print(data)
	if data[0] == '':
		break
socketClient.close()
curr_time = time.time()
print('Sending website in %f secs' % (curr_time-start_time))
print('CLLODESL')

time_tcp = curr_time-start_time
f = open(args.filename, "a+")
f.write(str(time_tcp))
f.write('\n')
