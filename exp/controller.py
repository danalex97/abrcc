import asyncio
import atexit
import os
import traceback
import time
import signal

from argparse import Namespace 
from pathlib import Path
from threading import Thread
from typing import List, Optional

from server.process import SubprocessStream, kill_subprocess 
from server.server import ctx_component, Component, JSONType, post_after, post_after_async
from scripts.network import Network
from threading import Thread


class BackendProcessor(SubprocessStream):
    def __init__(self, 
        cmd: List[str], 
        path: Path,
        name: str,
        frontend: SubprocessStream,
    ) -> None:
        super().__init__(cmd)

        # we want to flush all the time to keep the log
        self.quic_log = open(path / f'{name}_quic.log', 'a', buffering=1) 
        self.frontend = frontend

    def on_exit(self) -> None:
        self.quic_log.close()

    async def on_stdout(self, line: str) -> None:
        if line == "\n":
            pass
        print(line, end='')

    async def on_stderr(self, line: str) -> None:
        self.quic_log.write(line)
        print(line, end='')
        if 'Finished storing videos' in line:
            try:
                await self.frontend.start()
            except Exception as e:
                print(f'[frontend error] {e}')
                traceback.print_exc()


class Controller:
    def __init__(self,
        name: str,
        site: str,
        cc: str,
        network: Network,
        dash: List[str],
        quic_port: int, 
        only_server: bool,
        port: int,
        path: Path,
        leader_port: Optional[int] = None,
    ) -> None:
        self.dash = dash
        self.only_server = only_server
        self.port = port
        self.quic_port = quic_port

        directory = Path(os.path.dirname(os.path.realpath(__file__)))
        script = str(directory / '..' / 'quic' / 'run.sh')
        
        ports = ['--port', f"{quic_port}", '-mp', f"{port}", '--site', site]
        self.chrome  = SubprocessStream(
            [script] + ports + ['--chrome', '--profile', name]
        ) 
        self.backend = BackendProcessor( 
            cmd=[script, '--port', f"{quic_port}", '-mp', f"{port}"] +
                sum([['-d', str(d)] for d in dash] if dash else [], ['-s']) + 
                ['--site', site, '--profile', name, '--cc', cc] + 
                (['--certs'] if not leader_port else []),
            path=path,
            name=name,
            frontend=self.chrome,
        )
        self.network = network
        self.leader_port = leader_port

        if not self.only_server:
            Thread(target=self.start).start()

    def start(self) -> None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(post_after({}, 1000, '/init', self.port))

    @ctx_component
    async def on_init(self, json: JSONType) -> JSONType:
        try:
            await self.backend.start()
        except Exception as e:
            print(f'[backend error] {e}')
            traceback.print_exc()
        return 'OK'

    @ctx_component
    async def on_start(self, json: JSONType) -> JSONType:
        if self.only_server:
            return 'OK'
        elif not self.leader_port:
            # Start the network simulation
            await self.network.run(same_process=True)
            return 'OK'
        elif self.leader_port:
            # Let the leader starts the network and wait for it to 
            # tell us it's all ok
            await post_after({'port' : self.quic_port}, 0, "/start", port=self.leader_port)
            return 'OK'

    @ctx_component
    async def on_complete(self, json: JSONType) -> JSONType:
        # wait for others then, destroy myself
        await self.chrome.stop()
        await self.backend.stop()

        if not self.leader_port:
            # destroy myself
            post_after_async({'port' : self.quic_port}, 0, '/destroy', self.port)
        else:
            await post_after({'port' : self.quic_port}, 0, '/destroy', self.leader_port)
            post_after_async({'port' : self.quic_port}, 0, '/destroy', self.port)
        return 'OK'

    @ctx_component
    async def on_destroy(self, json: JSONType) -> JSONType:
        # Kill all chrome instances if I'm alone
        if not self.only_server and not self.leader_port:
            os.system("pkill -9 chrome")
        
        # Kill myself
        kill_subprocess(os.getpid())
        
        return 'OK'
