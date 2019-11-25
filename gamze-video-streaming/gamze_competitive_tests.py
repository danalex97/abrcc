import subprocess
import argparse
import numpy as np
import signal
import sys
import os
import psutil
import json
import logging as log
import sys
from time import sleep
import threading
import modules.config as config
from tempfile import SpooledTemporaryFile as tempfile
import multiprocessing
from multiprocessing.connection import Client
import logging
import datetime
import shutil


# settings
NETWORK_TRACES_PATH = 'network_traces/'
RUN_SCRIPT = 'gamze_run_browser_test.py'
RANDOM_SEED = 42
COOLDOWN_TIME = config.COOLDOWN_TIME
controller_connection = None

VIDEO_BITRATE = [300,750,1200,1850,2850,4300]  # Kbps

PROXY_SERVER_TCP_PORT_OFFSET = 8000 # Proxy servers are allocated TCP ports in the range 8000-8099
ABR_SERVER_TCP_PORT_OFFSET = 6000 # Proxy servers are allocated TCP ports in the range 6000-6099
PROXY_SERVER_UDP_PORT_OFFSET = 6100 # Proxy servers are allocated UDP ports in the range 6100-6199
VIDEO_SERVER_UDP_PORT_OFFSET = 6200 # Video servers are allocated UDP ports in the range 6200-6299

available_bw = multiprocessing.Value('d', 0) # variable shared between processes
traces = [[], []]
ports = []
streams = {} # for each stream it contains data, such as number of chunks downloaded or buffer occupancy
proxy_server_procs = {}
video_server_procs = {}


# timeout if running for too long (t + 30s)
def timeout_handler(signum, frame):
    raise Exception("Timeout")


# end all subprocesses
def end_processes():
    # controller_proc.terminate()
    tcp_traffic_proc.terminate()
    tcp_traffic_client_proc.terminate()
    proxy_server_procs.terminate()
    video_server_procs.terminate()


# start 'run_browser_test' with the necessary information for the logfile
def start_ABR(test_id, name, trace, abr, stream_id, duration, server_address, udp, quic):
    script = ['python', RUN_SCRIPT, abr, duration, server_address, './testresults/' + test_id, str(stream_id), trace]

    # print(' '.join(str(e) for e in script))
    # script = ['python', RUN_SCRIPT, abr, duration, server_address, './testresults/'+test_id+'/log_'+test_id+'_'+str(run_nr)+'_'+name]
    if udp:
        script.append('-u')
    if quic == 'true':
        script.append('-q')
    if args.browser:
        script.append('-b')

    # proc = subprocess.call(script, shell=False) # synchronous
    proc = subprocess.Popen(' '.join(str(e) for e in script), stdout=subprocess.PIPE, shell=True)  # asynchronous
    output = proc.stdout.readline()
    proc.wait()


#   read json config of test-setup and run it _repeat_n times
def runTest(testcase):
    udp = True if testcase['udp'] == 'true' else False

    # number of repetitions
    n = int(testcase['repeat_n'])

    # repeat this test_setup n times
    for i in range(n):

        # prepare jobs to be run
        job_threads = []
        j = 0
        for job in testcase['jobs']:
            server = server_config['server'][job['transport']]['address'] + ':' + \
                     server_config['server'][job['transport']]['port']
            t = threading.Timer(interval=float(job['start']), function=start_ABR,
                                args=[testcase['test_id'], job['name'], testcase['trace'], job['abr'], j,
                                      job['duration'], server, udp, job['quic']])
            job_threads.append(t)
            j += 1


        abr = job['abr']
        network_traces = NETWORK_TRACES_PATH + testcase['trace']
        trace_log = 'testresults/' + testcase['test_id'] + '/traces/traces' + '.txt'
        cwnd_folder = './testresults/' + testcase['test_id'] + '/cwnd'
        udp = udp
        num_servers = len(testcase['jobs'])
        init_c(network_traces, trace_log)
        if udp:
            start_udp_infrastructure(num_servers, cwnd_folder)

        global p_c, ports
        manager = multiprocessing.Manager()
        ports = manager.list()

        p_c = multiprocessing.Process(target=run_traces, args=(abr, trace_log, ports, udp, num_servers))
        p_c.start()

        # start jobs
        for t in job_threads:
            t.start()

        for t in job_threads:
            t.join()

            # stop network shaping script
        sleep(COOLDOWN_TIME)

def init_c(network_traces, trace_log):
    with open(network_traces, 'r') as trace_file:
        for line in trace_file:
            content = line.split('\t')
            traces[0].append(float(content[0]))
            traces[1].append(float(content[1].split('\n')[0]))
    open(trace_log, 'w').close() # empties the trace_log file
    logging.getLogger("urllib3").setLevel(logging.WARNING) # surpresses logging information from urllib3 module


# For each stream over UDP we create one proxy server and one video server
def start_udp_infrastructure(num_servers, cwnd_folder):
    for i in range(num_servers):
        proxy_server_http_port = PROXY_SERVER_TCP_PORT_OFFSET + i
        proxy_server_udp_port = PROXY_SERVER_UDP_PORT_OFFSET + i
        video_server_udp_port = VIDEO_SERVER_UDP_PORT_OFFSET + i

        proxy_server_script = ['python3', './udp_video_transfer/proxy_server.py', \
                               str(proxy_server_http_port), str(proxy_server_udp_port), str(video_server_udp_port)]
        proxy_server_proc = subprocess.Popen(proxy_server_script, shell=False)
        proxy_server_procs[i] = proxy_server_proc

        video_server_script = ['python2', './udp_video_transfer/gamze_video_server.py', \
                               str(video_server_udp_port), str(proxy_server_udp_port), str(i), cwnd_folder]
        video_server_proc = subprocess.Popen(video_server_script, shell=False)
        video_server_procs[i] = video_server_proc

def run_traces(abr, trace_log, ports, udp, num_servers):
    global time, available_bw
    traces_length = len(traces[0])
    i = 0
    available_bw.value = traces[1][0]
    sys.stdout.write(str(available_bw.value))
    sys.stdout.write("\n")

    os.system('sudo /sbin/tc qdisc del dev lo root')  # Make sure that all qdiscs are reset
    sys.stdout.write(str(udp))
    if udp:
        # If we run the video stream over UDP, we only want to throttle the UDP port. The reason being that the implementation
        # requires the proxy server to have an arbitrarily quick TCP connection to the video player.
        # TBF requires you to specify 'burst'. For 10mbit/s on Intel, you need at least 10kbyte buffer if you want to reach your configured rate!
        os.system('sudo /sbin/tc qdisc add dev lo root handle 1: prio')
        os.system('sudo /sbin/tc qdisc add dev lo parent 1:3 handle 30: tbf rate ' + str(
            available_bw.value) + 'mbit latency 2000ms burst 20000')# peakrate ' + str(peakrate) +'mbit mtu 1024')

        throttle_msg = 'Throttling bandwidth on ports '
        for j in range(num_servers):
            throttle_msg += str(VIDEO_SERVER_UDP_PORT_OFFSET + j) + ' '
            os.system('sudo /sbin/tc filter add dev lo protocol ip parent 1:0 prio 3 u32 match ip sport ' + str(
                VIDEO_SERVER_UDP_PORT_OFFSET + j) + ' 0xffff flowid 1:3')
        os.system('sudo /sbin/tc filter add dev lo protocol ip parent 1:0 prio 3 u32 match ip sport ' + str(
            5600) + ' 0xffff flowid 1:3')

        sys.stdout.write(throttle_msg)

    else:
        print('Throttling bandwidth: ' + str(available_bw.value) + ' Mbps')
        os.system('sudo ifconfig lo mtu 1500')  # set the mtu to the size of an ethernet frame to avoid jumbo frames
        os.system('sudo /sbin/tc qdisc add dev lo root tbf rate ' + str(
            available_bw.value) + 'mbit latency 200000ms burst 200000')

    while True:
        time = traces[0][i]
        available_bw.value = traces[1][i]
        print(str(time) + ' ' + str(available_bw.value))

        time = datetime.datetime.now()
        time_str = datetime.time(time.hour, time.minute, time.second, time.microsecond)
        with open(trace_log, 'a+') as f:
            f.write(str(time_str) + '\n' + str(available_bw.value) + '\n')

        if udp:
            os.system('sudo /sbin/tc qdisc change dev lo parent 1:3 handle 30: tbf rate ' + str(
                available_bw.value) + 'mbit latency 2000ms burst 20000')
        else:
            os.system('sudo /sbin/tc qdisc change dev lo root tbf rate ' + str(
                available_bw.value) + 'mbit latency 2000ms burst 20000')
        try:
            sleep(traces[0][i + 1] - traces[0][i])
        except KeyboardInterrupt:
            time = datetime.datetime.now()
            time_str = datetime.time(time.hour, time.minute, time.second, time.microsecond)
            f.write(str(time_str) + '\n' + str(available_bw.value) + '\n')
        i = (i + 1) % (traces_length - 1)


# This function must be called before the program terminates. Otherwise, the bandwidth will remain throttled.
def successful_termination():
    end_process(p_c)
    # time = datetime.datetime.now()
    # time_str = datetime.time(time.hour, time.minute, time.second, time.microsecond)
    # with open(trace_log, 'a+') as f:
    #     f.write(str(time_str) + '\n' + str(available_bw.value) + '\n')
    print('Bandwidth is no longer being throttled.')
    os.system('sudo ifconfig lo mtu 9000')
    os.system('sudo /sbin/tc qdisc del dev lo root')

def end_process(process):
    for proc in process.children(recursive=True):
        proc.send_signal(signal.SIGINT)
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=10)
    except psutil.TimeoutExpired:
        print("timeout expired closing network script")

def init():
    # parse server config
    global server_config
    with open(args.server_config) as json_data:
        server_config = json.load(json_data)
    log.info("loading json complete: " + str(server_config))

    global testcases_data
    testcases_data = []

    # read testcase json files
    log.info('creating output folders')

    for testcase_fname in args.testcases_list:
        with open(testcase_fname) as json_data:
            testcase = json.load(json_data)
            testcase['fname'] = testcase_fname
            testcases_data.append(testcase)

    # create folders
    for testcase in testcases_data:
        if os.path.exists('./testresults/' + testcase['test_id']):
            shutil.rmtree('./testresults/' + testcase['test_id'])
        if not os.path.exists('./testresults/' + testcase['test_id']):
            os.mkdir('./testresults/' + testcase['test_id'], 0755)  # for python3 it should be 0o755 instead
            os.mkdir('./testresults/' + testcase['test_id'] + '/traces', 0755)
            os.mkdir('./testresults/' + testcase['test_id'] + '/tcpdump', 0755)
            os.mkdir('./testresults/' + testcase['test_id'] + '/setup', 0755)
            os.mkdir('./testresults/' + testcase['test_id'] + '/cwnd', 0755)
        with open('./testresults/' + testcase['test_id'] + '/setup/' + testcase['test_id'] + '.json', 'w') as outfile:
            json.dump(testcase, outfile)

    if args.tcp_traffic:
        # generate background TCP traffic
        tcp_filename = './testresults/' + testcase['test_id'] + '/tcp.txt'
        global tcp_traffic_proc
        tcp_traffic_script = ['python', './web-traffic-generator/tcp_traffic_server.py']
        tcp_traffic_proc = subprocess.Popen(tcp_traffic_script, shell=False)
        sys.stdout.write("Generate TCP traffic")
        global tcp_traffic_client_proc
        tcp_traffic_client_script = ['python', './tcp_traffic.py', str(tcp_filename)]
        tcp_traffic_client_proc = subprocess.Popen(tcp_traffic_client_script, shell=False)
        print('run_client************************')


# define main function to capture interrupts
def main():
    # enable logging
    log.basicConfig(stream=sys.stderr, level=log.DEBUG)
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('server_config', help='json file containing server information', type=str)
    parser.add_argument('testcases_list', help='testcase filenames', nargs="+", type=str)
    parser.add_argument("-t", "--tcp_traffic", action="store_true",
                        help='parameter to add background TCP traffic')
    parser.add_argument("-b", "--browser", action="store_true", 
                        help='parameter to not open browser')
    global args
    args = parser.parse_args()

    os.system('./release.sh') # to deallocate all necessary ports
    init()

    # run tests
    for i, testcase in enumerate(testcases_data):
        runTest(testcase)
        log.info('compledted: ' + str(i) + '/' + str(len(testcases_data)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupted.")
        try:
            successful_termination()
            end_processes()
            sys.exit(0)
        except SystemExit:
            successful_termination()
            end_processes()
            os._exit(0)
