import asyncio
import os

from argparse import Namespace 
from pathlib import Path
from threading import Thread
from typing import List, Optional

from server.process import SubprocessStream, kill_subprocess 
from server.server import component, Component, JSONType, post_after
from scripts.network import Network


class BackendProcessor(SubprocessStream):
    def __init__(self, 
        cmd: List[str], 
        path: Path,
        name: str,
        frontend: SubprocessStream,
    ) -> None:
        super().__init__(cmd)
        self.quic_log = open(path / f'{name}_quic.log', 'a') 
        self.frontend = frontend

    async def on_stdout(self, line: str) -> None:
        if line == "\n":
            pass
        print(line, end='')

    async def on_stderr(self, line: str) -> None:
        self.quic_log.write(line)
        print(line, end='')
        if 'Finished storing videos' in line:
            await self.frontend.start()


class Controller:
    def __init__(self,
        name: str,
        network: Network,
        dash: List[str],
        only_server: bool,
        port: int,
        path: Path,
        leader_port: Optional[int] = None,
    ) -> None:
        self.dash = dash
        self.only_server = only_server
        self.port = port
       
        directory = Path(os.path.dirname(os.path.realpath(__file__)))
        script = str(directory / '..' / 'quic' / 'run.sh')
        
        self.chrome  = SubprocessStream(
            [script, '--chrome']
        ) 
        self.backend = BackendProcessor( 
            cmd=[script, '-s', '-d', 'record', '--certs'],
            path=path,
            name=name,
            frontend=self.chrome,
        )
        self.network = network
        self.leader_port = leader_port

        if not self.only_server:
            Thread(target = self.start).start() 

    def start(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(post_after(
            data = {},
            wait = 1000,
            resource = '/init',
            port = self.port,
        ))

    async def init(self):
        await self.backend.start()

    def do_nothing(self) -> Component:
        @component
        async def do_nothing(json: JSONType) -> JSONType:
            return 'OK'
        return do_nothing

    def on_init(self) -> Component:
        @component
        async def init(json: JSONType) -> JSONType:
            await self.init()
            return 'OK'
        return init  

    def on_start(self) -> Component:
        if self.only_server:
            return self.do_nothing()
        @component
        async def on_start(json: JSONType) -> JSONType:
            if not self.leader_port:
                # Start the network simulation
                await self.network.run(same_process=True)
                return 'OK'
            else:
                # Let the leader starts the network and wait for it to 
                # tell us it's all ok
                await post_after({'port' : self.port}, 0, "/", port=self.leader_port)
                return 'OK'
        return on_start

    def on_complete(self) -> Component:
        if self.only_server:
            return self.do_nothing()
        @component
        async def on_complete(json: JSONType) -> JSONType:
            # killing child subprocesses
            self.chrome.stop()
            self.backend.stop()
            
            # kill myself later 
            if not self.leader_port:
                await post_after({}, 0, '/destroy', self.port)
            else:
                await post_after({'pid' : os.getpid()}, 0, '/destroy', self.leader_port)
            return 'OK'
        return on_complete

    def on_destroy(self) -> Component:
        @component
        async def on_destroy(json: JSONType) -> JSONType:
            os.system("kill $(pgrep chrome)")
            kill_subprocess(os.getpid())
            return 'OK'
        return on_destroy
