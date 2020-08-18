import argparse
import socket
import sys
import time


def main(args: argparse.Namespace) -> None:
    DATA_LENGTH = 100000
    host, port = "localhost", args.port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        while True:
            received = sock.recv(DATA_LENGTH)
    except socket.error as exc:
        if exc.errno == 111:
            time.sleep(.1)
            main(args)
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    main(parser.parse_args()) 
