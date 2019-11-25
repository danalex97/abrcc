#!/usr/bin/python

#
# written by @eric_capuano
# https://github.com/ecapuano/web-traffic-generator
#
# published under MIT license :) do what you want.
#
#20170714 shyft ADDED python 2.7 and 3.x compatibility and generic config
from __future__ import print_function 
import requests, re, time, random 
from socket import *
import argparse

try:
	import config
except ImportError:
	class ConfigClass: #minimal config incase you don't have the config.py
		clickDepth = 1 # how deep to browse from the rootURL
		minWait = 1 # minimum amount of time allowed between HTTP requests
		maxWait = 2 # maximum amount of time to wait between HTTP requests
		debug = True # set to True to enable useful console output

		# use this single item list to test how a site responds to this crawler
		# be sure to comment out the list below it.
		#rootURLs = ["https://digg.com/"] 
		rootURLs = [
				"https://digg.com/",
				"https://www.yahoo.com",
				"http://www.cnn.com",
				"http://www.ebay.com",
				"https://en.wikipedia.org/wiki/Main_Page",
				"https://austin.craigslist.org/",
				"https://www.google.com/",
				"https://ethz.ch/de.html",
				"https://drive.google.com/",
				"https://www.apple.com/",
				"https://www.youtube.com/"
			]


		# items can be a URL "https://t.co" or simple string to check for "amazon"
		blacklist = [
			'facebook.com',
			'pinterest.com'
			]  

		# must use a valid user agent or sites will hate you
		userAgent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) ' \
			'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'
	config = ConfigClass 

def HTTPServer(url,content):
	global socketServer
	f= open('youtube.html',"w+")
	f.write(content)
	# socketServer.sendall(content)

def doRequest(url):
	global dataMeter
	global goodRequests
	global badRequests
	global intervals
	global i
	start_time = time.time()
	
	if config.debug:
		print("requesting: %s" % url)
	
	headers = {'user-agent': config.userAgent}
	
	try:
		r = requests.get(url, headers=headers, timeout=5)
	except:
		time.sleep(30) # else we'll enter 100% CPU loop in a net down situation
		return False
		
	status = r.status_code
	
	pageSize = len(r.content)
	dataMeter = dataMeter + pageSize
	
	if config.debug:
		print("Page size: %s" % pageSize)
		if ( dataMeter > 1000000 ):
			print("Data meter: %s MB" % (dataMeter / 1000000))
		else:
			print("Data meter: %s bytes" % dataMeter)
	
	if ( status != 200 ):
		badRequests+=1
		if config.debug:
			print("Response status: %s" % r.status_code)
		if ( status == 429 ):
			if config.debug:
				print("We're making requests too frequently... sleeping longer...")
			sleepTime+=30
	else:
		goodRequests+=1
		st_time = time.time()
		print('************************************************************************')
        HTTPServer(url, r.content)
        print('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA')
        # data = socketServer.recv(1024)
        fn_time = time.time()
        print(fn_time-st_time)
        print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
	
	# need to sleep for random number of seconds!
	if config.debug:
		print("Good requests: %s" % goodRequests)
		print("Bad reqeusts: %s" % badRequests)		
	
	time.sleep(100)
	curr_time = time.time()
	if curr_time - start_time < intervals[i]:
		sleepTime = intervals[i] - (curr_time - start_time)
		print("Sleeping for %s seconds..." % sleepTime)
		time.sleep(sleepTime)
	i += 1
	return r

def browse(urls):
	currURL = 10# random.randint(0,(len(config.rootURLs)-1))

	page = doRequest(urls[currURL])  # hit current root URL
		
	if config.debug:
		print("Done.")


# define main function to capture interrupts
def main():

	# initialize our global variables
    global dataMeter
    global goodRequests
    global badRequests
    dataMeter = 0
    goodRequests = 0
    badRequests = 0

    # global socketServer
    # socketServer = socket(AF_INET, SOCK_STREAM)
    # socketServer.bind(('localhost', 20010))
    # socketServer.connect(('localhost', 20000))

    global intervals
    lmbda = 1
    intervals = [random.expovariate(lmbda) for k in range(500)]
    timestamps = [0.0]
    timestamp = 0.0
    for t in intervals:
        timestamp += t
        timestamps.append(timestamp)
	# plt.figure()
	# plt.scatter([0,1,2,3,4,5,6,7,8,9], intervals)
	# plt.show()
    print(intervals)
    global i
    i = 0

    while True:
        print("Traffic generator started...")
        print("----------------------------")
        print("https://github.com/ecapuano/web-traffic-generator")
        print("")
        print("Clicking %s links deep into %s different root URLs, " \
        	% (config.clickDepth,len(config.rootURLs)))
        print("waiting between %s and %s seconds between requests. " \
        	% (config.minWait,config.maxWait))
        print("")
        print("This script will run indefinitely. Ctrl+C to stop.")
        browse(config.rootURLs)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupted.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
