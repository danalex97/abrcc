import os.path, sys # need this to be able to import server.server for priveleged processes
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

from server.server import ctx_component, Component, JSONType

import argparse
import os
import uuid

from pathlib import Path
from subprocess import Popen 
from typing import List, Tuple, Optional


DEFAULT_CACHE_SIZE = 100
DEFAULT_CONNECTIONS = 50
DEFAULT_INSTANCES = 5
START_PORT = 6815


def generate_traffic(
    port: int, 
    cache: int, 
    connections: int, 
    time_log_path: Optional[str] = None,
    light: bool = True,
    single_flow: bool = False,
) -> Tuple[Popen, Popen]:
    """
    Return a pair of (server, client) proceses that generate background short-flow
    TCP traffic(when `single_flow` = False) or a single long TCP traffic flow(when 
    `single_flow` = True).
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    exec_dir = str(Path(dir_path) / '..')

    if not single_flow:
        server_script = 'traffic_server.py'
        client_script = 'traffic_client.py'
    else:
        server_script = 'single_flow_server.py'
        client_script = 'single_flow_client.py'

    client_extra = []
    server_extra = []
    if time_log_path:
        if not single_flow:
            client_extra += ['--time-log', str(Path(exec_dir) / time_log_path)]
        else:
            client_extra += ['--log-file', str(Path(exec_dir) / time_log_path)] 
    if light and not single_flow:
        server_extra += ['--light']

    if not single_flow:
        server_extra += ['--cache', str(cache)]
        client_extra += ['--connections', str(connections)]

    server = Popen([
        'python3', str(Path(dir_path) / server_script), '--port', f"{port}", 
    ] + server_extra, cwd=exec_dir)
    client = Popen([
        'python3', str(Path(dir_path) / client_script), '--port', f"{port}",
    ] + client_extra , cwd=exec_dir)
    
    return server, client


class TrafficGenerator: 
    start_port: int
    instances: int
    running: List[Popen]
    time_log_path: Optional[str]
    single_flow: bool 

    def __init__(self, 
        start_port: int = START_PORT, 
        instances: Optional[int] = None,
        time_log_path: Optional[str] = None,
        light: bool = True,
        single_flow: bool = False,
    ) -> None:
        self.start_port = start_port
        self.instances = instances
        self.running = []
        self.time_log_path = time_log_path
        self.light = light
        self.single_flow = single_flow
        if self.single_flow and not self.instances:
            self.instances = 1
        elif not self.instances:
            self.instances = DEFAULT_INSTANCES

    @property
    def ports(self) -> List[int]:
        return [self.start_port + i for i in range(self.instances)] 
    
    @ctx_component
    async def on_start(self, json: JSONType) -> JSONType:
        for i in range(self.instances):
            log_id = str(uuid.uuid1())[:8]
            if not self.single_flow:
                log_file = str(Path(self.time_log_path) / f'fct_{log_id}.log')
            else:
                log_file = str(Path(self.time_log_path) / f'mbps_{log_id}.log')
            server, client = generate_traffic(
                self.start_port + i, 
                DEFAULT_CACHE_SIZE, 
                DEFAULT_CONNECTIONS,
                log_file,
                self.light,
                self.single_flow,
            ) 
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
    server, client = generate_traffic(
        args.port, 
        args.cache, 
        args.connections, 
        single_flow=args.single_flow,
    )
    
    server.wait()
    client.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    parser.add_argument('--cache', metavar='-s', type=int, help='Cache size in MB.', 
        default=DEFAULT_CACHE_SIZE)
    parser.add_argument('--connections', metavar='-c', type=int, help='Number of connections.', 
        default=DEFAULT_CONNECTIONS)
    parser.add_argument('--single-flow', action='store_true', help='Use single flow.')
    main(parser.parse_args()) 
