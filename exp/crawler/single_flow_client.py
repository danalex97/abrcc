import argparse
import os
import time
import subprocess
import sys
import signal

def main(args: argparse.Namespace) -> None:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    os.system(f'g++ -o {dir_path}/socket_client {dir_path}/socket_client.cpp')
    while True:
        try:
            if args.log_file != None:
                subprocess.call(f'{dir_path}/socket_client {args.port} {args.log_file}', shell=True)
            else:
                subprocess.call(f'{dir_path}/socket_client {args.port}', shell=True)
        except subprocess.CalledProcessError as exp:
            time.sleep(.1)
        except Exception as exp:
            sys.exit(-1)

if __name__ == "__main__":
    def signal_handler(signal, frame):
        sys.exit(-1)
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    parser.add_argument('--log-file', type=str, help='Log file path for the link load.')
    main(parser.parse_args()) 
