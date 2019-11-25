'''
Program to plot the contents of logfiles

Author: Josua Hug (modified script from the pensieve-paper)

Note: Some logfiles have a wrong name format. Thus, this program will through an out of bound
exception.
'''

import argparse
import os, logging
from sets import Set

import matplotlib.pyplot as plt
import numpy as np
from modules import mqoe

NUM_BINS = 100
BITS_IN_BYTE = 8.0
MILLISEC_IN_SEC = 1000.0
M_IN_B = 1000000.0
VIDEO_LEN = 64
VIDEO_BIT_RATE = [350, 600, 1000, 2000, 3000]
COLOR_MAP = plt.cm.jet #nipy_spectral, Set1,Paired 
SIM_DP = 'sim_dp'


def main():
	read_cmd_arguments()
	global NAMES #get all players names
	NAMES=get_all_schemes(args.testcases_logs)
	print('schemes: ' + str(NAMES))

	time_all = {}
	bit_rate_all = {}
	buff_all = {}
	bw_all = {}
	rebuff_all = {}
	raw_reward_all = {}
	dl_all={}

	for scheme in NAMES:
		time_all[scheme] = {}
		raw_reward_all[scheme] = {}
		bit_rate_all[scheme] = {}
		buff_all[scheme] = {}
		bw_all[scheme] = {}
		dl_all[scheme] = {}


	#parse logfiles
	for log_file in args.testcases_logs:

		filename=log_file.split('/')[-1]
		print('filename='+filename)
		name=filename.split('_')[3]

		time_ms = []
		bit_rate = []
		rebuff = []
		buff = []
		bw = []
		dl = []
		reward = []

		with open(log_file, 'rb') as f:
			for line in f:
				if line == '\n':
					break
				parse = line.split()
				if len(parse) <= 1:#break if video ended
					break
				#time_ms.append(float(parse[0]))
				time_ms.append(get_time(parse[0]))
				bit_rate.append(int(parse[1]))
				buff.append(float(parse[2]))
				rebuff.append(float(parse[3]))
				dl.append(float(parse[4])/1000.0) #chunk size in bytes
				bw.append(float(parse[4]) / float(parse[5]) * BITS_IN_BYTE * MILLISEC_IN_SEC / M_IN_B) # bandwidth = video_chunk_size / download_time
				reward.append(float(parse[6]))
		
		time_ms = np.array(time_ms)

		dl_acc = []
		#sum up download bits
		for i in xrange(len(dl)):
			dl_acc.append(sum(dl[:i]))
		
		time_all[name]=time_ms
		bit_rate_all[name]=bit_rate
		buff_all[name]=buff
		bw_all[name]=bw
		rebuff_all[name] = rebuff
		raw_reward_all[name]=reward
		dl_all[name]=dl_acc

	time_start = min(min(time_all[s]) for s in NAMES)
	for s in NAMES:
		time_all[s]-=time_start

	#plot bandwidth, bitrate, buffer

	#decide colors for schemes
	new_colormap = [COLOR_MAP(i) for i in np.linspace(0, 1, len(NAMES))]
	colors = {}
	for i,scheme in enumerate(NAMES):
		colors[scheme] = new_colormap[i]

	fig = plt.figure()

	# plot bitrate decisions
	ax = fig.add_subplot(211)
	# ax.set_xlabel('time (s)')
	ax.get_yaxis().set_ticks([300,750,1200,1850,2850,4300]) #bitrates of testvideo

	for scheme in NAMES:
		ax.plot(time_all[scheme][:], bit_rate_all[scheme][:], label=scheme,drawstyle='steps-pre', marker='.', color=colors[scheme])

	filename=args.testcases_logs[0].split('/')[-1]
	title=filename.split('_')[1]
	plt.title(title+'\nruns: '+str(get_run_numbers(args.testcases_logs)))
	plt.ylabel('bit rate (kbps)')
	ax.legend(loc=4, borderaxespad=0.)


	#add additional proints to visualize buffer drain (1s drain for 1s play)
	buffer_drain_time= {}
	buffer_drain_blevel={}
	for scheme in NAMES:
		buffer_drain_time[scheme] = []
		buffer_drain_blevel[scheme] = []

		#starting point
		buffer_drain_time[scheme].append(time_all[scheme][0]-rebuff_all[scheme][0])
		buffer_drain_blevel[scheme].append(0.0)
		buffer_drain_time[scheme].append(time_all[scheme][0])
		buffer_drain_blevel[scheme].append(buff_all[scheme][0])
		for i in range(1,len(time_all[scheme])):
			x = time_all[scheme][i]
			buffer_drain_time[scheme].append(x)
			buffer_drain_blevel[scheme].append(buff_all[scheme][i-1]-(time_all[scheme][i]-time_all[scheme][i-1]))
			buffer_drain_time[scheme].append(x)
			buffer_drain_blevel[scheme].append(buff_all[scheme][i])


	#plot buffer levels
	ax2 = fig.add_subplot(212, sharex=ax)

	# plot reported buffer levels
	for scheme in NAMES:
		ax2.plot(time_all[scheme][:], buff_all[scheme][:], label=str(scheme), marker = '+', color = colors[scheme])

	# plot buffer drain visualisation
	for scheme in NAMES:
		ax2.plot(buffer_drain_time[scheme][:], buffer_drain_blevel[scheme][:], linestyle=':', color=colors[scheme])

	ax2.axhline(y=0, xmin=0, xmax=1, color='black')
	plt.ylabel('buffer size (sec)')
	plt.xlabel('time (sec)')
	#ax2.legend(loc=4, borderaxespad=0.)
	'''


	# plot experienced bandwidths
	ax3 = fig.add_subplot(413, sharex=ax)
	for scheme in NAMES:
		ax3.plot(time_all[scheme][:], bw_all[scheme][:], label=str(scheme), color=colors[scheme])
	#ax3.axhline(y=2.0, xmin=0, xmax=1, color='green')#draw line on half the bandwidth
	#ax3.legend(loc=4, borderaxespad=0.)
	plt.ylabel('bandwidth (mbps)')
	plt.xlabel('time (sec)')

	#plot total downloaded bits
	ax4 = fig.add_subplot(414, sharex=ax)
	for scheme in NAMES:
		ax4.plot(time_all[scheme], dl_all[scheme], label=scheme, color=colors[scheme])
	#ax4.legend(loc=4, borderaxespad=0.)
	plt.ylabel('total downloaded (kB)')
	# plt.xlabel('time (sec)')
	'''


	# print debug information
	SCHEMES_REW = []
	qoe_list = []
	quality_qoe_list = []
	switch_qoe_list = []
	rebuffer_qoe_list = []
	l = int(0)
	for scheme in NAMES:
		qoe = mqoe.QOE(time_all[scheme], bit_rate_all[scheme], rebuff_all[scheme])
		print("QOE(%s): %5.3f" % (scheme, qoe))
		qoe_list.append(qoe)
		SCHEMES_REW.append(scheme + ':  %.2f' % (mqoe.QOE(time_all[scheme][:], bit_rate_all[scheme][:], rebuff_all[scheme][:])))
		l = max(l, len(time_all[scheme][:]))
	print("Average QOE: %5.3f" % (np.mean(qoe_list)))
	print("fairness: %.2f" % (mqoe.qoe_fairness(qoe_list, mqoe.QOE(l*[0], l*[4300], l*[0]), 0)))
	for scheme in NAMES:
		quality_qoe = mqoe.quality_QOE(time_all[scheme], bit_rate_all[scheme], rebuff_all[scheme])
		print("Quality QOE(%s): %5.3f" % (scheme, quality_qoe))
		quality_qoe_list.append(quality_qoe)
		SCHEMES_REW.append(scheme + ':  %.2f' % (mqoe.quality_QOE(time_all[scheme][:], bit_rate_all[scheme][:], rebuff_all[scheme][:])))
		l = max(l, len(time_all[scheme][:]))
	print("Average Quality QOE: %5.3f" % (np.mean(quality_qoe_list)))

	for scheme in NAMES:
		switch_qoe = mqoe.switch_QOE(time_all[scheme], bit_rate_all[scheme], rebuff_all[scheme])
		print("Switch QOE(%s): %5.3f" % (scheme, switch_qoe))
		switch_qoe_list.append(switch_qoe)
		SCHEMES_REW.append(scheme + ':  %.2f' % (mqoe.switch_QOE(time_all[scheme][:], bit_rate_all[scheme][:], rebuff_all[scheme][:])))
		l = max(l, len(time_all[scheme][:]))
	print("Average Switch QOE: %5.3f" % (np.mean(switch_qoe_list)))

	for scheme in NAMES:
		rebuffer_qoe = mqoe.rebuffer_QOE(time_all[scheme], bit_rate_all[scheme], rebuff_all[scheme])
		print("Rebuffer QOE(%s): %5.3f" % (scheme, rebuffer_qoe))
		rebuffer_qoe_list.append(rebuffer_qoe)
		SCHEMES_REW.append(scheme + ':  %.2f' % (mqoe.rebuffer_QOE(time_all[scheme][:], bit_rate_all[scheme][:], rebuff_all[scheme][:])))
		l = max(l, len(time_all[scheme][:]))
	print("Average Rebuffer QOE: %5.3f" % (np.mean(rebuffer_qoe_list)))
	#plt.figlegend(loc='lower center', ncol=5, labelspacing=0.)
	plt.show()

def get_time(time_stamp):
    parsed_time = time_stamp.split(':')
    return (float)(parsed_time[0]) * 3600 + (float)(parsed_time[1]) * 60 + (float)(parsed_time[2])

def get_all_schemes(logfiles):
	schemes=Set()
	for logfile in logfiles:
		filename=logfile.split('/')[-1]
		print(filename.split('_'))
		name=filename.split('_')[3]
		schemes.add(name)
	return schemes

def get_run_numbers(logfiles):
	schemes=Set()
	for logfile in logfiles:
		filename=logfile.split('/')[-1]
		run_nr=filename.split('_')[2]
		schemes.add(run_nr)
	return schemes


def read_cmd_arguments():
	parser = argparse.ArgumentParser()
	#parser.add_argument('--testcase_config', help='path to json file with the testcase information', type=str)
	parser.add_argument('testcases_logs', help='testcase logfiles (logfiles of dash-localhost-server)', nargs="+", type=str)
	parser.add_argument('-v', '--verbose', help='change verbosity level', type=int)
	global args
	args=parser.parse_args()


	if args.verbose:
		logging.basicConfig(level=args.verbose)

if __name__ == '__main__':
	main()
