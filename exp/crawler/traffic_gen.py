import os.path, sys # need this to be able to import server.server for priveleged processes
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

from server.server import ctx_component, Component, JSONType

import argparse
import os

from pathlib import Path
from subprocess import Popen 
from typing import List, Tuple


DEFAULT_CACHE_SIZE = 100
DEFAULT_CONNECTIONS = 50
DEFAULT_INSTANCES = 5
START_PORT = 8815


def generate_traffic(port: int, cache: int, connections: int) -> Tuple[Popen, Popen]:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    exec_dir = str(Path(dir_path) / '..')

    server_script = 'traffic_server.py'
    client_script = 'traffic_client.py'

    server = Popen([
        'python3', str(Path(dir_path) / server_script), '--port', f"{port}", 
        '--cache', f"{cache}"
    ], cwd=exec_dir)
    client = Popen([
        'python3', str(Path(dir_path) / client_script), '--port', f"{port}",
        '--connections', f"{connections}"
    ], cwd=exec_dir)
    
    return server, client


class TrafficGenerator: 
    start_port: int
    instances: int
    running: List[Popen]

    def __init__(self, 
        start_port: int = START_PORT, 
        instances: int = DEFAULT_INSTANCES,
    ) -> None:
        self.start_port = start_port
        self.instances = instances
        self.running = []

    @property
    def ports(self) -> List[int]:
        return [self.start_port + i for i in range(self.instances)] 
    
    @ctx_component
    async def on_start(self, json: JSONType) -> JSONType:
        for i in range(self.instances):
            server, client = generate_traffic(self.start_port + i, DEFAULT_CACHE_SIZE, DEFAULT_CONNECTIONS) 
            self.running.append(client)
            self.running.append(server)
        return 'OK'

    @ctx_component
    async def on_complete(self, json: JSONType) -> JSONType:
        for process in self.running:
            process.kill()
        return 'OK'


class EmptyTrafficGenerator(TrafficGenerator):
    @property
    def ports(self) -> List[int]:
        return [] 
    
    @ctx_component
    async def on_start(self, _: JSONType) -> JSONType:
        return 'OK'

    @ctx_component
    async def on_complete(self, _: JSONType) -> JSONType:
        return 'OK'


def main(args: argparse.Namespace) -> None:
    server, client = generate_traffic(args.port, args.cache, args.connections)
    
    server.wait()
    client.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    parser.add_argument('--cache', metavar='-s', type=int, help='Cache size in MB.', 
        default=DEFAULT_CACHE_SIZE)
    parser.add_argument('--connections', metavar='-c', type=int, help='Number of connections.', 
        default=DEFAULT_CONNECTIONS)
    main(parser.parse_args()) 
