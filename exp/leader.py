import asyncio 
import shutil
import os
import time

from enum import Enum
from typing import Dict
from argparse import ArgumentParser, Namespace
from pathlib import Path
from threading import Thread

from components.plots import LivePlot
from server.server import ctx_component, do_nothing, JSONType, Server, post_after
from server.process import kill_subprocess 
from scripts.network import Network


class InstanceState(Enum):
    STARTED = 0
    STOPPED = 1
    
class Instance:
    def __init__(self) -> None:
        self.state = InstanceState.STARTED
    
    def stop(self) -> None:
        self.state = InstanceState.STOPPED
    

class LeaderController:
    instances: Dict[int, Instance]
    all_started: asyncio.Event
    all_stopped: asyncio.Event

    def __init__(self,
        instances: int,
        network: Network,
        port: int,
    ) -> None:
        self.nbr_instances = instances
        self.network = network
        self.port = port
        
        self.instances = {}
        self.all_started = asyncio.Event()
        self.all_stopped = asyncio.Event()

    @property
    def started(self):
        return len([x.state == InstanceState.STARTED for x in self.instances.values()])

    @property
    def stopped(self):
        return len([x.state == InstanceState.STOPPED for x in self.instances.values()])

    @ctx_component
    async def on_start(self, json: JSONType) -> JSONType:
        port = json['port']
        self.instances[port] = Instance()

        # Wait for all instances to start
        if self.started == self.nbr_instances:
            self.all_started.set()
            # Once all instances have started, we can start the network simulation
            await self.network.run(same_process=True)
        await self.all_started.wait()
        return 'OK'

    @ctx_component
    async def on_destroy(self, json: JSONType) -> JSONType:
        port = json['port']
        self.instances[port].stop() 
    
        # Wait for all instances to stop 
        if self.stopped == self.nbr_instances:
            self.all_stopped.set()
            
            # kill all remaining chrome instances
            os.system("kill $(pgrep chrome)")
            Thread(target=self.finalize).start()
        
        await self.all_stopped.wait()
        return 'OK'
    
    def finalize(self) -> None:
        time.sleep(5)
        kill_subprocess(os.getpid())

def run(args: Namespace) -> None:
    path = Path(args.path)

    shutil.rmtree(path, ignore_errors=True)
    os.system(f"mkdir -p {path}")

    controller = LeaderController(
        instances = args.instances,
        network = Network(
            bandwidth=getattr(args, 'bandwidth', None),
            delay=getattr(args, 'delay', None),
            trace_path=getattr(args, 'trace', None),
        ),
        port = args.port,
    )
    
    server = Server('experiment', args.port)

    (server
        .add_post('/start', controller.on_start())
        .add_post('/destroy', controller.on_destroy()))

    plots = {}
    if args.plot:
        plots = {
            'qoe' : LivePlot(figure_name='qoe', y_label='qoe'),
            'rebuffer' : LivePlot(figure_name='rebuffer', y_label='rebuffer'),
            'switch' : LivePlot(figure_name='switch', y_label='switch'),
            'quality' : LivePlot(figure_name='quality', y_label='quality'),
        }
        (server
            .add_post('/qoe', plots['qoe'])
            .add_post('/rebuffer', plots['rebuffer'])
            .add_post('/switch', plots['switch'])
            .add_post('/quality', plots['quality']))
    else:
        (server
            .add_post('/qoe', do_nothing)
            .add_post('/rebuffer', do_nothing)
            .add_post('/switch', do_nothing)
            .add_post('/quality', do_nothing))

    server.run()


if __name__ == "__main__":
    parser = ArgumentParser(description='Run an experiment leader.')
    parser.add_argument('instances', type=int, help='Number of instances.')
    parser.add_argument('--port', type=int, default=8800, help='Port(default 8800).')
    parser.add_argument('--path', type=str, default='logs/default', help='Experiment folder path.')
    parser.add_argument('-l', '--delay', type=float,  help='Delay of the link.')
    parser.add_argument('-b', '--bandwidth', type=float, help='Bandwidth of the link.')
    parser.add_argument('-t', '--trace', type=str, help='Trace of bandwidth.')
    parser.add_argument('--plot', action='store_true', help='Enable plotting.')
    run(parser.parse_args())   
