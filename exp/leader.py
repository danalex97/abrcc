import asyncio 
import shutil
import os
import time

from enum import Enum
from typing import Dict, Optional
from argparse import ArgumentParser, Namespace
from pathlib import Path
from threading import Thread

from components.plots import LivePlot
from components.complete import OnComplete
from server.server import ctx_component, multiple_sync, do_nothing, JSONType, Server, post_after
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
    _all_started: Optional[asyncio.Event]
    _all_stopped: Optional[asyncio.Event]

    def __init__(self,
        instances: int,
        network: Network,
        port: int,
    ) -> None:
        self.nbr_instances = instances
        self.network = network
        self.port = port
        
        self.instances = {}
        self._all_started = None 
        self._all_stopped = None

    @property
    def all_started(self):
        if self._all_started is None:
            self._all_started = asyncio.Event()
        return self._all_started

    @property
    def all_stopped(self):
        if self._all_stopped is None:
            self._all_stopped = asyncio.Event()
        return self._all_stopped
    
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
        self.network.add_port(port)

        print(f'[leader] Start sync > {port}')
        # Wait for all instances to start
        if self.started == self.nbr_instances:
            self.all_started.set()
            # Once all instances have started, we can start the network simulation
            await self.network.run(same_process=True)
        
        await self.all_started.wait()
        print(f'[leader] Start done > {port}')
        
        return 'OK'

    @ctx_component
    async def on_destroy(self, json: JSONType) -> JSONType:
        port = json['port']
        self.instances[port].stop() 
    
        # Wait for all instances to stop 
        print(f'[leader] Destroy sync > {port}')
        if self.stopped == self.nbr_instances:
            self.all_stopped.set()
            Thread(target=self.finalize).start()
          
        await self.all_stopped.wait()
        print(f'[leader] Destroy done > {port}')
        
        return 'OK'
    
    def finalize(self) -> None:
        time.sleep(5)
        print('[leader] Finalization')

        # kill all remaining chrome instances and myself
        os.system("kill $(pgrep chrome)")
        kill_subprocess(os.getpid())

def run(args: Namespace) -> None:
    path = Path(args.path)

    print(f'Running leader with {args.instances} instances.')
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
    
    directory = Path(os.path.dirname(os.path.realpath(__file__)))
    script = str(directory / '..' / 'quic' / 'run.sh')
    os.system(f'{script} --certs')

    server = Server('experiment', args.port)

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

    (server
        .add_post('/start', controller.on_start())
        .add_post('/destroy', multiple_sync(
            OnComplete(path, 'leader', plots), 
            controller.on_destroy(),
         )))
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
