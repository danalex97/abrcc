import argparse
import socketserver
import threading
import random
import string
import time


socketserver.TCPServer.allow_reuse_address = True
DATA_LENGTH = 100000
UPDATE_LOG_SECS = 2


def random_string(size: int) -> str:
    return ''.join(random.choice(
        string.ascii_uppercase + 
        string.ascii_lowercase +
        string.digits
    ) for _ in range(size))


def main(args: argparse.Namespace) -> None:
    class SingleFlowHandler(socketserver.BaseRequestHandler):
        def handle(self):
            log_file = None
            if args.log_file:
                log_file = open(args.log_file, 'w')
            start, sent_data, calls = time.time(), 0, 0
            while True:
                calls += 1
                data = random_string(DATA_LENGTH) 
                self.request.send(bytes(data, 'utf-8'))
                sent_data += len(data)

                update_time = time.time() - start
                if update_time > UPDATE_LOG_SECS:
                    print(sent_data, update_time, calls)
                    speed = 8 * sent_data / 1000 / 1000 / update_time
                    print(f'Link speed {speed} mbps')
                    start, sent_data, calls = time.time(), 0, 0

                    if log_file:
                        log_file.write(f'{speed:.6}\n')
                        log_file.flush()

    host, port = "localhost", args.port
    server = socketserver.TCPServer((host, port), SingleFlowHandler)
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    parser.add_argument('--log-file', type=str, help='Log file path for the link load.')
    main(parser.parse_args()) 
