from socket import *
import time
import os
import sys

BASE_PATH = '/var/www/html/websites'
os.system('sudo fuser -k -n tcp 5601')
socketServer = socket(AF_INET, SOCK_STREAM)
socketServer.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
socketServer.bind(('localhost', 5600))
socketServer.listen(10000000)
# conn, addr = socketServer.accept()
i = 0
while True:
	conn, addr = socketServer.accept()
	data = conn.recv(1024)
	request = data.decode()
	print(request)
	f = open(request, 'r')
	data = f.read()
	conn.sendall(data)
	i += 1
	print("Number of request ................... %d" % i)
	conn.close()
	print('closed')
	if(i==6):
		socketServer.close()
		break
