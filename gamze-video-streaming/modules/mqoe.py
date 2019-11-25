'''
    Script to analyze the tests, parses log files, calculates QoE
    Author: jhug

'''

import argparse, os, json, string, logging, math
import numpy as np
import operator
from collections import namedtuple

ABRs = ['BB', 'RB', 'robustMPC', 'fastMPC', 'RL']
CCs = ['cubic', 'bbr']
Abr = namedtuple('Abr', ['abr', 'cc', 'quic'])

PENALTY_STARTTIME = 0.0 # 0.0
PENALTY_REBUF = 4.3 #4.3
PENALTY_QSWITCH = 1.0 # 1.0
BOOST_QUALITY = 1.0 # 1.0

K_in_M = 1000.0

# calculate qoe from read in timestamps, quality data and rebuffer time, return averate over number of downloaded junks
def QOE(time, quality, rebuffer):
    n = min(len(time), len(quality), len(rebuffer))
    if n != 0 and len(time) == len(quality) and len(quality) == len(rebuffer):
        qoe = rawQOE(time,quality, rebuffer)/n
    else:
        logging.error("Array lengths do not match or are 0: " + "time=%d, quality=%d, rebuffer=%d" % (len(time), len(quality), len(rebuffer)))
        qoe = 0
    return qoe

def quality_QOE(time, quality, rebuffer):
    n = min(len(time), len(quality), len(rebuffer))
    if n != 0 and len(time) == len(quality) and len(quality) == len(rebuffer):
        n = min(len(time), len(quality), len(rebuffer))
        qoe = 0

        if n > 0:
            for i in range(1, n):
                qoe += quality[i] / K_in_M * BOOST_QUALITY
            qoe += quality[0] / K_in_M * BOOST_QUALITY
        else:
            qoe = 0
    else:
        logging.error("Array lengths do not match or are 0: " + "time=%d, quality=%d, rebuffer=%d" % (len(time), len(quality), len(rebuffer)))
        qoe = 0
    return qoe

def switch_QOE(time, quality, rebuffer):
    n = min(len(time), len(quality), len(rebuffer))
    if n != 0 and len(time) == len(quality) and len(quality) == len(rebuffer):
        n = min(len(time), len(quality), len(rebuffer))
        qoe = 0

        if n > 0:
            for i in range(1, n):
                qoe += - PENALTY_QSWITCH * math.fabs(quality[i] - quality[i - 1])/K_in_M
        else:
            qoe = 0
    else:
        logging.error("Array lengths do not match or are 0: " + "time=%d, quality=%d, rebuffer=%d" % (len(time), len(quality), len(rebuffer)))
        qoe = 0
    return qoe

def rebuffer_QOE(time, quality, rebuffer):
    n = min(len(time), len(quality), len(rebuffer))
    if n != 0 and len(time) == len(quality) and len(quality) == len(rebuffer):
        n = min(len(time), len(quality), len(rebuffer))
        qoe = 0

        if n > 0:
            for i in range(1, n):
                qoe += - PENALTY_REBUF * rebuffer[i]
            qoe +=  - PENALTY_STARTTIME * rebuffer[0]
        else:
            qoe = 0
    else:
        logging.error("Array lengths do not match or are 0: " + "time=%d, quality=%d, rebuffer=%d" % (len(time), len(quality), len(rebuffer)))
        qoe = 0
    return qoe

def rawQOE(time,quality,rebuffer):
    n = min(len(time), len(quality), len(rebuffer))
    qoe = 0

    if n > 0:
        for i in range(1, n):
            qoe += quality[i] / K_in_M * BOOST_QUALITY - PENALTY_REBUF * rebuffer[i] - PENALTY_QSWITCH * math.fabs(
                quality[i] - quality[i - 1])/K_in_M
        qoe += quality[0] / K_in_M * BOOST_QUALITY - PENALTY_STARTTIME * rebuffer[0]
    else:
        qoe = 0
    return qoe

# calculates the QoE fairness F = 1 - (2o / (H - L))
# where H is the highest QoE and L the lowest, o is the standard deviation
def qoe_fairness(qoe, high, low):
    std = np.std(np.array(qoe), axis=0)
    f = 1.0 - 2.0*std / (high - low)
    return f


# calculates jains index given the experienced bandwidths of different players
# optimal = 1, worst = 1/n
def jain_index(values):
    n=len(values)
    s = sum(values)
    sq = map(lambda x: x**2, values)
    return math.pow(s,2)/(n*sq)

#parses logfile and returns data: (timestamps[], quality[], rebufferTime[])
def parse_logfile(filename):
    listTime = []
    listQual = []
    listDelta = []

    with open(filename, 'r') as f:
        for line in f:

            if line == '\n':
                break
            else:
                line.split('\t')
                a, b, c, d, e, f, g = [float(i) for i in line.split('\t')]
                listTime.append(a)
                listQual.append(b)
                listDelta.append(d)

    if not (len(listTime)==len(listQual) and len(listQual) == len(listDelta) and len(listDelta) > 0):
        logging.error('Error parsing file: '+filename)

    return listTime, listQual, listDelta

# returns qoe of a pensieve-server log
def qoe_of_file(filename):
    t,q,d = parse_logfile(filename=filename)
    return QOE(time=t,quality=q,rebuffer=d)
