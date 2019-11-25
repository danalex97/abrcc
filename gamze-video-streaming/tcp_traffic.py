import argparse
import random
import matplotlib.pyplot as plt
from threading import Timer
import os
import sys
import time
import selenium
import subprocess
import signal
import argparse
from selenium import webdriver
from pyvirtualdisplay import Display
from selenium.webdriver.chrome.options import Options
from time import sleep
import re
import httplib
import urllib
import requests
import psutil

#parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('filename', type=str)
args=parser.parse_args()

lmbda = 0.5
intervals = [20.491921734377712, 0.35838527143778504, 30.07350136756547, 101.249258959991, 6.963782080923449, 27.89669421727359] #[random.expovariate(lmbda) for i in range(10)]
websites = ['ebay', 'google', 'youtube', 'cnn', 'yahoo', 'wikipedia']
timestamps = [0.0]
timestamp = 0.0
for t in intervals:
    timestamp += t
    timestamps.append(timestamp)
print(intervals)

timeout = False
i = 0
while True:
	time.sleep(intervals[i])
	start_time = time.time()
	client_script = ['python', './web-traffic-generator/client.py', str(args.filename), websites[i]]
	client = subprocess.Popen(client_script, shell=False)
	i += 1
	print('////////////////////////////////////////////////////////////')
	print(i)
	if i == 6:
		break

