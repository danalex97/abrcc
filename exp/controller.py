import asyncio
import os
import signal
import subprocess
import psutil

from pathlib import Path
from threading import Thread
from typing import Awaitable, IO, List, Optional

from server import component, Component, JSONType, post_after


def kill_subprocess(process: subprocess.Popen) -> None:
    parent = psutil.Process(process.pid)
    for child in parent.children(recursive=True):
        child.kill()
    parent.kill()


async def _read_stream(stream: IO[str], callback: Optional[Awaitable]) -> None:  
    while True:
        line = await stream.readline()
        if line:
            if callback is not None:
                await callback(line)
        else:
            break


class Stream:
    def __init__(self):
        self.process = None
    
    async def create(self, cmd: List[int]) -> subprocess.Popen:
        self.process = await asyncio.create_subprocess_exec(*cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        return self.process

    async def start(self, stdout_cb: Awaitable, stderr_cb: Awaitable) -> None:
        await asyncio.wait([    
            _read_stream(self.process.stdout, stdout_cb),
            _read_stream(self.process.stderr, stderr_cb),
        ])


class Controller:
    def __init__(self, 
        bw: Optional[int], 
        delay: Optional[int],
        dash: List[int],
        only_server: bool,
        port: int,
        path: Path,
    ) -> None:
        self.bw = bw
        self.delay = delay
        self.dash = dash
        self.only_server = only_server
        self.port = port
        self.quic_log = open(path / 'quic.log', 'a') 

        if not self.only_server:
            Thread(target = self.start).start() 

        self.backend = None
        self.chrome = None

    def start(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(post_after(
            data = {},
            wait = 1000,
            resource = '/init',
            port = self.port,
        ))

    def get_script(self) -> str:
        path = Path(os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "..",
        ))
        return str(path / 'quic' / 'run.sh')

    async def on_new_line(self, line: str):
        if line == "\n":
            pass
        print(line, end='')

    async def on_new_err(self, line: str):
        if line == "\n":
            pass
        self.quic_log.write(line)
        print(line, end='')
        if 'Finished storing videos' in line:
            stream = Stream()
            self.chrome = await stream.create([self.get_script(), '--chrome'])
            await stream.start(None, None)

    async def init(self):
        stream = Stream()
        self.backend = await stream.create([self.get_script(), '-s', '-d', 'record'])
        await stream.start(
            lambda x: self.on_new_line(x.decode("utf-8")),
            lambda x: self.on_new_err(x.decode("utf-8")),
        )

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
            return 'OK'
        return on_start

    def on_complete(self) -> Component:
        if self.only_server:
            return self.do_nothing()

        @component
        async def on_complete(json: JSONType) -> JSONType:
            # killing child subprocesses
            kill_subprocess(self.chrome)
            kill_subprocess(self.backend)
            os.system("kill $(pgrep chrome)")
            
            # kill myself later 
            await post_after(
                data = {},
                wait = 5000,
                resource = '/destroy',
                port = self.port,
            )
            return 'OK'
        return on_complete

    def on_destroy(self) -> Component:
        @component
        async def on_destroy(json: JSONType) -> JSONType:
            os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)
            return 'OK'
        return on_destroy
