import asyncio
import subprocess
import psutil

import os
import signal

from typing import Awaitable, IO, List, Optional


def kill_subprocess(
    pid: int, 
    without_parent: bool = False, 
    sig: int = signal.SIGUSR1,
) -> None:
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try: 
                os.kill(child.pid, sig)
            except:
                pass
        try:
            if not without_parent:
                os.kill(parent.pid, sig)
        except:
            pass
    except:
        pass


async def _read_stream(stream: IO[str], callback: Awaitable) -> None:  
    while True:
        line = await stream.readline()
        if line:
            line = line.decode('utf-8')
            await callback(line)
        else:
            break


class SubprocessStream:
    """
    Asyncio wrapper over process. 
    Usage example:
        await SubprocessStream().start()
    """
    def __init__(self, cmd: List[str]):
        self.__cmd = cmd

    @property 
    def process(self) -> subprocess.Popen:
        return self.__process

    async def on_stdout(self, line: str) -> None:
        pass

    async def on_stderr(self, line: str) -> None:
        pass

    async def stop(self) -> None:
        try:
            await asyncio.wait_for(self.future, timeout=1.0)
        except:
            pass
       
        kill_subprocess(self.process.pid)
        await asyncio.wait([self.future])

    async def start(self, 
        stdout_cb: Optional[Awaitable] = None, 
        stderr_cb: Optional[Awaitable] = None,
    ) -> None:
        self.__process = await asyncio.create_subprocess_exec(*self.__cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        on_stdout = stdout_cb if stdout_cb else self.on_stdout
        on_stderr = stderr_cb if stderr_cb else self.on_stderr
        
        self.future = asyncio.ensure_future(asyncio.wait([    
            _read_stream(self.process.stdout, self.on_stdout),
            _read_stream(self.process.stderr, self.on_stderr),
        ]))
