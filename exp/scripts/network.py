import os.path, sys
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

import asyncio
import sys
import os

from argparse import ArgumentParser, Namespace
from typing import List, Optional
from server.process import SubprocessStream


TC = '/sbin/tc'


def run_cmd(cmd: str) -> None:
    print(f"> {cmd}")
    os.system(cmd)


class Network:
    def __init__(self, 
        delay: Optional[float] = None,
        bandwidth: Optional[float] = None,
        trace_path: Optional[str] = None,
        burst: int = 20000,
        ports: List[int] = [6121],
        skip: bool = False,
    ) -> None:
        self.delay = delay
        self.bandwidth = bandwidth
        self.trace_path = trace_path
        self.burst = burst
        self.ports = ports
        self.first = not skip
        self.trace = None

        self.setup_traffic_class()
        self.add_port_filters()
    
    def add_port(self, port: int) -> None:
        if port not in self.ports:
            self.ports.append(port)
            self.add_port_filters(ports=[port])

    def set_trace(self) -> None:
        if self.trace_path is None:
            return
        to_timestamp = lambda x: tuple(map(float, x))
        with open(self.trace_path, 'r') as f:
            content = f.read()
            content.replace('\t', ' ')
            self.trace = [
                to_timestamp(line.split())
                for line in content.split('\n')
                if line != ''
            ]

    def setup_traffic_class(self) -> None:
        run_cmd(f'{TC} qdisc del dev lo root')   
        run_cmd(f'{TC} qdisc add dev lo root handle 1: prio')   
        run_cmd(f'{TC} qdisc add dev lo parent 1:3 handle 30: tbf ' + 
                f'rate 10mbit latency 10ms burst {self.burst}')
        
    def add_port_filters(self, ports: Optional[List[int]] = None) -> None:
        if ports is None:
            ports = self.ports 
        for port in ports:
            run_cmd(f'{TC} filter add dev lo protocol ip parent 1: prio 3 u32 ' +  
                    f'match ip sport {port} 0xffff flowid 1:3')

    def set_conditions(self, bw: Optional[float] = None):
        if bw is None:
            bw = self.bandwidth if not self.trace else self.trace[0][1] 
        if bw is None:
            run_cmd(f'{TC} qdisc del dev lo root')
            return
        bw = format(bw, '.3f')
        
        cmd    = f'{TC} qdisc change dev lo handle 30:'
        run_cmd(f'{cmd} tbf rate {bw}mbit latency {self.delay}ms burst {self.burst}')

    async def process(self) -> None:
        async def process_timestamp(wait: float, bw_value: float) -> None: 
            await asyncio.sleep(wait)
            self.set_conditions(bw_value)
        if self.trace:
            await asyncio.gather(*[
                process_timestamp(wait, bw_value)
                for wait, bw_value in self.trace
            ])
   
    async def run(self, same_process: bool = True) -> None:
        if same_process:
            self.set_conditions()
            asyncio.ensure_future(self.process())
        else:
            script = str(os.path.realpath(__file__))
            cmd = (['python3', script, '-s'] +
                (['-d', str(self.delay)] if self.delay else []) + 
                (['-b', str(self.bandwidth)] if self.bandwidth else []) + 
                (['-t', str(self.trace_path)] if self.trace_path else []) + 
                (['--burst', str(self.burst)] if self.burst else []) + 
                sum([['-p', str(p)] for p in self.ports], []) 
            )
            await SubprocessStream(cmd).start()


if __name__ == "__main__":
    parser = ArgumentParser(description='Setup network conditions.')
    parser.add_argument('-d', '--delay', type=int, default=10,  help='Delay of the link.')
    parser.add_argument('-b', '--bandwidth', type=int, help='Bandwidth of the link.')
    parser.add_argument('--burst', type=int, default=20000, help='Burst.')
    parser.add_argument('-t', '--trace', dest='trace_path', type=str, help='Trace for bandwidth.')
    parser.add_argument('-p', '--port', type=int, action='append', dest='ports', help='Port to limit traffic on.')
    parser.add_argument('-s', '--skip', action='store_true', help='Skip setup and run trace.') 
    args = parser.parse_args()

    if args.ports == None:
        args.ports = [6212]

    loop = asyncio.get_event_loop()
    loop.run_until_complete(Network(**vars(args)).run())
