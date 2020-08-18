import argparse
import socketserver
import threading
import random
import string
import time


socketserver.TCPServer.allow_reuse_address = True
DATA_LENGTH = 1024
UPDATE_LOG_SECS = 2


def random_string(size: int) -> str:
    return ''.join(random.choice(
        string.ascii_uppercase + 
        string.ascii_lowercase +
        string.digits
    ) for _ in range(size))


class SingleFlowHandler(socketserver.BaseRequestHandler):
    def handle(self):
        start, sent_data = time.time(), 0
        while True:
            data = random_string(DATA_LENGTH) 
            self.request.send(bytes(data, 'utf-8'))
            sent_data += len(data)

            if time.time() - start > UPDATE_LOG_SECS:
                print(f'Link speed {8 * sent_data / 1000 / 1000 / UPDATE_LOG_SECS} mbps')
                start, sent_data = time.time(), 0


def main(args: argparse.Namespace) -> None:
    host, port = "localhost", args.port
    server = socketserver.TCPServer((host, port), SingleFlowHandler)
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    main(parser.parse_args()) 
