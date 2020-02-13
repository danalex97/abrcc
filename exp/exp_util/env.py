from argparse import Namespace
from subprocess import Popen
from typing import Callable, Dict

import os
import time


__EXPERIMENTS = {}


def experiments() -> Dict[str, Callable[[Namespace], None]]:
    return __EXPERIMENTS


def experiment(f: Callable[[Namespace], None]) -> Callable[[Namespace], None]:
    global __EXPERIMENTS
    __EXPERIMENTS[f.__name__] = f
    return f


def run_cmd(cmd: str) -> None:
    print(f'[Experiment runnner] > {cmd}') 
    os.system(cmd)


def run_cmd_async(cmd: str) -> Popen:
    print(f'[Experiment runner] > {cmd}')
    return Popen([arg for arg in cmd.split(' ') if len(arg) > 0])


def run_cmds(leader_cmd: str, cmd1: str, cmd2: str) -> None:
    leader = run_cmd_async(leader_cmd)
    time.sleep(1)
    instance1 = run_cmd_async(cmd1)
    time.sleep(20)
    instance2 = run_cmd_async(cmd2)

    leader.wait()
    instance1.wait()
    instance2.wait()

def run_subexp(
    bandwidth: int, 
    latency: int, 
    path: str, 
    server1: str, 
    server2: str, 
    force_run: bool = False,
    burst: int = 20000,
) -> None:
    if os.path.isdir(path) and not force_run:
        return   
    leader_cmd = (
        f"python3 leader.py -b {bandwidth} -l {latency} --port 8800 2 --path {path} --plot --burst {burst}"
    )
    cmd1 = (
        f"python3 run.py --port 8001 --quic-port 4001 -lp 8800 {server1} --path {path}"
    )
    cmd2 = (
        f"python3 run.py --port 8002 --quic-port 4002 -lp 8800 {server2} --path {path}"
    )
    run_cmds(leader_cmd, cmd1, cmd2)

def run_trace(
    path: str, 
    server: str,
    force_run: bool = False,
):
    if os.path.isdir(path) and not force_run:
        return   
    ports = "--port 8001 --quic-port 4001"
    extra = "--burst 2000 --plot"
    cmd = (
        f"python3 run.py {ports} {server} {extra} --path {path}"
    )
    instance = run_cmd_async(cmd)
    instance.wait()
