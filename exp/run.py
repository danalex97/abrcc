from argparse import ArgumentParser

from monitor import log_metrics  
from server import Server


if __name__ == "__main__":
    parser = ArgumentParser(description='')
    parser.add_argument('--port', type=int, default=8080, help='Port(default 8008).')
    args = parser.parse_args()
    
    (Server('experiment', args.port)
        .add_post('/metrics', log_metrics)
        .run())

