from argparse import ArgumentParser

from monitor import Monitor 
from server import Server, multiple


if __name__ == "__main__":
    parser = ArgumentParser(description='')
    parser.add_argument('--port', type=int, default=8080, help='Port(default 8080).')
    parser.add_argument('--path', type=str, default='logs/log.txt', help='Path of the monitor.')
    args = parser.parse_args()
    
    monitor = Monitor(args.path)
    (Server('experiment', args.port)
        .add_post('/metrics', monitor)
        .run())
