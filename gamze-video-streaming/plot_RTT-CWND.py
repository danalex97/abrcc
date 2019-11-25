'''
Program to plot the contents of logfiles

Author: Josua Hug (modified script from the pensieve-paper)

Note: Some logfiles have a wrong name format. Thus, this program will through an out of bound
exception.
'''

import argparse
import os, logging
from sets import Set
import sys

import matplotlib.pyplot as plt
import numpy as np
from modules import mqoe
from operator import truediv

NUM_BINS = 100
BITS_IN_BYTE = 8.0
MILLISEC_IN_SEC = 1000.0
M_IN_B = 1000000.0
VIDEO_LEN = 64
VIDEO_BIT_RATE = [350, 600, 1000, 2000, 3000]
COLOR_MAP = plt.cm.jet  # nipy_spectral, Set1,Paired
SIM_DP = 'sim_dp'

def main():
    read_cmd_arguments()
    global NAMES_RTT  # get all players names
    NAMES_RTT = get_all_schemes(args.testcases_logs_RTT)
    print('schemes: ' + str(NAMES_RTT))

    time_all = {}
    RTT_all = {}
    estimated_RTT_all = {}
    timeout_all = {}
    rate_all = {}
    pace_all = {}

    for scheme in NAMES_RTT:
        time_all[scheme] = {}
        RTT_all[scheme] = {}
        estimated_RTT_all[scheme] = {}
        timeout_all[scheme] = {}
        rate_all[scheme] = {}
        pace_all[scheme] = {}

    # parse logfiles
    for log_file in args.testcases_logs_RTT:

        filename = log_file.split('/')[-1]
        print('filename=' + filename)
        name = filename.split('_')[1]

        time_ms = []
        RTT = []
        estimated_RTT = []
        timeout = []
        rate = []
        pace = []

        with open(log_file, 'rb') as f:
            for line in f:
                if line == '\n':
                    break
                parse = line.split()
                if len(parse) <= 1:  # break if video ended
                    break
                # time_ms.append(float(parse[0]))
                time_ms.append(get_time(parse[0]))
                RTT.append(float(parse[1]))
                estimated_RTT.append(float(parse[2]))
                timeout.append(float(parse[3]))
                rate.append(float(parse[4]))
                pace.append(float(parse[5]))

        time_ms = np.array(time_ms)
        time_all[name] = time_ms
        RTT_all[name] = RTT
        estimated_RTT_all[name] = estimated_RTT
        timeout_all[name] = timeout
        rate_all[name] = rate
        pace_all[name] = pace

    time_start = min(min(time_all[s]) for s in NAMES_RTT)
    for s in NAMES_RTT:
        time_all[s] -= time_start

    # plot bandwidth, bitrate, buffer

    # decide colors for schemes
    new_colormap = [COLOR_MAP(i) for i in np.linspace(0, 1, len(NAMES_RTT))]
    colors = {}
    for i, scheme in enumerate(NAMES_RTT):
        colors[scheme] = new_colormap[i]



    fig = plt.figure()

    # plot bitrate decisions
    ax = fig.add_subplot(711)
    # ax.set_xlabel('time (s)')
    for scheme in NAMES_RTT:
        ax.plot(time_all[scheme][:], RTT_all[scheme][:], label=str(scheme), marker='+', color=colors[scheme])

    filename = args.testcases_logs_RTT[0].split('/')[-1]
    title = filename.split('_')[1]
    plt.ylabel('RTT (s)')
    ax.legend(loc=4, borderaxespad=0.)

    # plot bitrate decisions
    ax = fig.add_subplot(712)
    # ax.set_xlabel('time (s)')
    for scheme in NAMES_RTT:
        ax.plot(time_all[scheme][:], estimated_RTT_all[scheme][:], label=str(scheme), marker='+', color=colors[scheme])

    filename = args.testcases_logs_RTT[0].split('/')[-1]
    title = filename.split('_')[1]
    plt.ylabel('ESTIMATED RTT (s)')
    ax.legend(loc=4, borderaxespad=0.)

    # plot bitrate decisions
    ax = fig.add_subplot(713)
    # ax.set_xlabel('time (s)')
    for scheme in NAMES_RTT:
        ax.plot(time_all[scheme][:], timeout_all[scheme][:], label=str(scheme), marker='+', color=colors[scheme])

    filename = args.testcases_logs_RTT[0].split('/')[-1]
    title = filename.split('_')[1]
    plt.ylabel('TIMEOUT (s)')
    ax.legend(loc=4, borderaxespad=0.)


    # plot bitrate decisions
    ax = fig.add_subplot(714)
    # ax.set_xlabel('time (s)')
    for scheme in NAMES_RTT:
        ax.plot(time_all[scheme][:], pace_all[scheme][:], label=str(scheme), marker='+', color=colors[scheme])

    filename = args.testcases_logs_RTT[0].split('/')[-1]
    title = filename.split('_')[1]
    plt.ylabel('Pace (s)')
    ax.legend(loc=4, borderaxespad=0.)

    # plot bitrate decisions
    ax = fig.add_subplot(715)
    # ax.set_xlabel('time (s)')
    for scheme in NAMES_RTT:
        ax.plot(time_all[scheme][:], rate_all[scheme][:], label=str(scheme), marker='+', color=colors[scheme])
        print(np.mean(rate_all[scheme][20:60]))

    filename = args.testcases_logs_RTT[0].split('/')[-1]
    title = filename.split('_')[1]
    plt.ylabel('rate (bps)')
    ax.legend(loc=4, borderaxespad=0.)







    global NAMES_qual  # get all players names
    NAMES_qual = get_all_schemes(args.testcases_logs_qual)
    print('schemes: ' + str(NAMES_qual))

    time_all = {}
    qual_all = {}


    for scheme in NAMES_qual:
        qual_all[scheme] = {}

    # parse logfiles
    for log_file in args.testcases_logs_qual:

        filename = log_file.split('/')[-1]
        print('filename=' + filename)
        name = filename.split('_')[1]

        time_ms = []
        qual = []

        with open(log_file, 'rb') as f:
            for line in f:
                if line == '\n':
                    break
                parse = line.split()
                if len(parse) <= 1:  # break if video ended
                    break
                # time_ms.append(float(parse[0]))
                time_ms.append(get_time(parse[0]))
                qual.append(float(parse[1])*1000)


        time_ms = np.array(time_ms)
        time_all[name] = time_ms
        qual_all[name] = qual

    time_start = min(min(time_all[s]) for s in NAMES_qual)
    for s in NAMES_qual:
        time_all[s] -= time_start

    # plot bandwidth, bitrate, buffer
    # decide colors for schemes
    new_colormap = [COLOR_MAP(i) for i in np.linspace(0, 1, len(NAMES_qual))]
    colors = {}
    for i, scheme in enumerate(NAMES_qual):
        colors[scheme] = new_colormap[i]
    ax = fig.add_subplot(716)
    for scheme in NAMES_qual:
        ax.plot(time_all[scheme][:], qual_all[scheme][:], label=str(scheme), marker='+', color=colors[scheme])
    filename = args.testcases_logs_qual[0].split('/')[-1]
    title = filename.split('_')[1]
    plt.ylabel('Determined Quality (bps)')
    ax.legend(loc=4, borderaxespad=0.)






    global NAMES  # get all players names
    NAMES = get_all_schemes(args.testcases_logs_CWND)
    print('schemes: ' + str(NAMES))

    time_all = {}
    CWND_rate_all = {}

    for scheme in NAMES:
        time_all[scheme] = {}
        CWND_rate_all[scheme] = {}

    # parse logfiles
    for log_file in args.testcases_logs_CWND:

        filename = log_file.split('/')[-1]
        print('filename=' + filename)
        name = filename.split('_')[1]

        time_ms = []
        CWND_rate = []

        with open(log_file, 'rb') as f:
            for line in f:
                if line == '\n':
                    break
                parse = line.split()
                if len(parse) <= 1:  # break if video ended
                    break
                # time_ms.append(float(parse[0]))
                time_ms.append(get_time(parse[0]))
                CWND_rate.append(int(parse[1]))

        time_ms = np.array(time_ms)
        time_all[name] = time_ms
        CWND_rate_all[name] = CWND_rate

    time_start = min(min(time_all[s]) for s in NAMES)
    for s in NAMES:
        time_all[s] -= time_start

    # decide colors for schemes
    new_colormap = [COLOR_MAP(i) for i in np.linspace(0, 1, len(NAMES))]
    colors = {}
    for i, scheme in enumerate(NAMES):
        colors[scheme] = new_colormap[i]

    # plot bitrate decisions
    ax = fig.add_subplot(717)
    # ax.set_xlabel('time (s)')
    for scheme in NAMES:
        ax.plot(time_all[scheme][:], CWND_rate_all[scheme][:], label=str(scheme), marker='+', color=colors[scheme])

    filename = args.testcases_logs_CWND[0].split('/')[-1]
    title = filename.split('_')[1]
    plt.ylabel('CWND (ppRTT)')
    ax.legend(loc=4, borderaxespad=0.)


    plt.show()


def get_time(time_stamp):
    parsed_time = time_stamp.split(':')
    return (float)(parsed_time[0]) * 3600 + (float)(parsed_time[1]) * 60 + (float)(parsed_time[2])


def get_all_schemes(logfiles):
    schemes = Set()
    for logfile in logfiles:
        filename = logfile
        print(filename.split('_'))
        name = filename.split('_')[4]
        schemes.add(name)
    return schemes


def get_run_numbers(logfiles):
    schemes = Set()
    for logfile in logfiles:
        filename = logfile.split('/')[-1]
        run_nr = filename.split('_')[2]
        schemes.add(run_nr)
    return schemes


def read_cmd_arguments():
    parser = argparse.ArgumentParser()
    print(str(len(sys.argv)))
    num = (len(sys.argv)-1) //3
    # num = len(sys.argv)-1
    # parser.add_argument('--testcase_config', help='path to json file with the testcase information', type=str)
    parser.add_argument('testcases_logs_RTT', help='testcase logfiles (logfiles of dash-localhost-server)', nargs=num,
                        type=str)
    parser.add_argument('testcases_logs_qual', help='testcase logfiles (logfiles of dash-localhost-server)', nargs=num,
                        type=str)
    parser.add_argument('testcases_logs_CWND', help='testcase logfiles (logfiles of dash-localhost-server)', nargs=num,
                        type=str)
    parser.add_argument('-v', '--verbose', help='change verbosity level', type=int)
    global args
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=args.verbose)


if __name__ == '__main__':
    main()