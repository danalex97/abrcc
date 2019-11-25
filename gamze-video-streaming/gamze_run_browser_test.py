#   runABR
#   script to do a single run of an ABR
#   by starting the localhost-server and a browser-session
#   arguments:
#   @abr_alg, @time, @server_address, @experiment_id

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

ABR_SERVER_PORT_OFFSET = 6000

# timeout if running for too long (t + 30s)
def timeout_handler(signum, frame):
	raise Exception("Timeout")
	
# end all subprocesses
def end_process(proc_pid):
    process = psutil.Process(proc_pid)
    for proc in process.children(recursive=True):
        proc.send_signal(signal.SIGINT)
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=10)
    except psutil.TimeoutExpired:
        print("timeout expired closing network script")

def wait_for_video_end(pipe_out, timeout):
    endtime = time.time() + timeout
    while time.time()<endtime:
        line = pipe_out.readline()
        if str.startswith(line, "done_successful"):
            return
    return

#main program
def run():
    #read input variables
    ABR_ALG = args.abr_alg #abr algorithm to execute
    TIME =  args.time_seconds# time to sleep ins seconds
    SERVER_ADDR = args.server_addr #server address to open
    STREAM_ID = str(args.stream_id)
    TRACE = args.trace
    EXP_ID = args.logpath+'/log_' + ABR_ALG + '_' + TRACE + '_' + STREAM_ID #path to logsile

    print >> sys.stderr, 'udp', args.udp
    if args.udp:
        url='http://localhost/' + 'myindex_' + ABR_ALG + '_udp.html'
    else:
        url='http://localhost/' + 'myindex_' + ABR_ALG + '.html'
        
    # timeout signal
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIME + 30)

    try:
        port = ABR_SERVER_PORT_OFFSET + args.stream_id
        # start abr algorithm server
        if ABR_ALG == 'GAMZE':
            command = ['python', './rl_server/gamze_server.py', str(port), EXP_ID, str(TIME)] #currently with BB
        elif ABR_ALG == 'RL':
            command = ['python', './rl_server/rl_server_no_training.py', str(port), EXP_ID]
        elif ABR_ALG == 'fastMPC':
            command = ['python', './rl_server/fast_mpc_server.py', str(port), EXP_ID]
        elif ABR_ALG == 'robustMPC':
            command = ['python', './rl_server/robust_mpc_server.py', str(port), EXP_ID]
        else:
            command = ['python', './rl_server/simple_server.py', str(port), ABR_ALG, EXP_ID]

        global proc
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        
        url += '?p=' + str(port)
        
        print(port) # This has to be the only print statement up to this point. This is because every time we call print, 
                    # its string is passed to compettitive_tests.py using pipes
        sys.stdout.flush()
        

        #r = requests.post('http://localhost:' + str(port), json={'suggested_bitrate': 4300})

        # to not display the page in browser (unless -b option)
        if args.show_browser:
            display = Display(visible=0, size=(300,400))
            display.start()

        #init chrome driver
	'''
        default_chrome_user_dir = 'abr_browser_dir/chrome_data_dir'
        chrome_user_dir = '/tmp/chrome_user_dir_id_'
        os.system('rm -r ' + chrome_user_dir)
        os.system('cp -r ' + default_chrome_user_dir + ' ' + chrome_user_dir)
        chrome_driver = 'abr_browser_dir/chromedriver'
	'''

        options = Options()
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--autoplay-policy=no-user-gesture-required')
        options.add_argument("--disable-infobars")
        options.add_argument('--disable-application-cache')
        options.add_argument('--media-cache-size=1')
        options.add_argument("--disk-cache-size=1")
        options.add_argument("--disable-web-security") # only needed when running tests over the UDP proxy
        options.add_argument("--explicitly-allowed-ports=6000")



        #enable quic
        if args.quic:
            options.add_argument('--no-proxy-server')
            options.add_argument('--enable-quic')
            options.add_argument('--quic-version=QUIC_VERSION_39')
            options.add_argument('--quic-host-whitelist="https://'+SERVER_ADDR+'" "https://'+SERVER_ADDR+'"')
            options.add_argument('--origin-to-force-quic-on='+SERVER_ADDR)


        # start chrome
        #driver=webdriver.Chrome(chrome_driver, chrome_options=options)
	driver_path = '/usr/local/lib/node_modules/webdriver-manager/selenium/chromedriver_75.0.3770.140'
        driver=webdriver.Chrome(chrome_options=options, executable_path=driver_path)
        driver.set_page_load_timeout(10)
        driver.get(url)

        #run for @TIME seconds
        wait_for_video_end(pipe_out=proc.stdout, timeout=TIME)
        print('Driver Quitted1')
        #end
        driver.quit()
        print('Driver Quitted2')
        if args.show_browser:
            display.stop()
        proc.send_signal(signal.SIGINT)
        proc.wait()
        


    except Exception as e:
        try:             
            display.stop()
        except:
            pass
        try:
            driver.quit()
        except:
            pass
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait()
        except:
            pass
	    print(e)

# define main function to capture interrupts
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('abr_alg', help='short name of abr algorithm', type=str)
    parser.add_argument('time_seconds', help='time in seconds', type=int)
    parser.add_argument('server_addr', help='server address, example localhost:2015', type=str)
    parser.add_argument('logpath', help='path of the logfile, usually: ./results/log_ABRNAME_INDEX.log', type=str)
    parser.add_argument('-v','--video', help='name of the video to test', type=str, default='testVideo')
    parser.add_argument('stream_id', help='id of stream in case multiple are running in parallel', type=int)
    parser.add_argument('trace', help='name of the trace file used', type=str)
    parser.add_argument('-u', '--udp', help='use UDP connection', action='store_true')
    parser.add_argument('-q', '--quic', help='enable quic', action='store_true')
    parser.add_argument('-b', '--show_browser', help='show browser window', action='store_true')
    global args
    args=parser.parse_args()

    run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupted.")
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait()
        except:
            pass
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
