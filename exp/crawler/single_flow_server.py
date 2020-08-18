import argparse
import os

def main(args: argparse.Namespace) -> None:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    os.system(f'g++ -o {dir_path}/socket_server {dir_path}/socket_server.cpp')
    if args.log_file != None:
        os.system(f'{dir_path}/socket_server {args.port} {args.log_file}')
    else:
        os.system(f'{dir_path}/socket_server {args.port}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    parser.add_argument('--log-file', type=str, help='Log file path for the link load.')
    main(parser.parse_args()) 
