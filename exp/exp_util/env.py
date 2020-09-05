from argparse import Namespace
from subprocess import Popen
from typing import Callable, Dict, List, Optional
from wrapt_timeout_decorator import timeout as timeout_func
from functools import wraps

from server.process import kill_subprocess 

import os
import time
import signal


__EXPERIMENTS = {}


def experiments() -> Dict[str, Callable[[Namespace], None]]:
    return __EXPERIMENTS


def experiment(f: Callable[[Namespace], None]) -> Callable[[Namespace], None]:
    """
    @experiment decorator

    Used to register runnable experiments in the `experiment.py` main script.
    """
    global __EXPERIMENTS
    __EXPERIMENTS[f.__name__] = f
    return f


def run_cmd(cmd: str) -> None:
    """
    Run a single command.
    """
    print(f'[Experiment runnner] > {cmd}') 
    os.system(cmd)


def run_cmd_async(cmd: str) -> Popen:
    """
    Start single command in a separate process and return the process.
    """
    print(f'[Experiment runner] > {cmd}')
    return Popen([arg for arg in cmd.split(' ') if len(arg) > 0])


def run_cmds(leader_cmd: str, cmds: List[str]) -> None:
    """
    Run a `leader_cmd` and a list of `cmds` that synchronize with the leader.
    """
    leader = run_cmd_async(leader_cmd)
    time.sleep(1)
    
    instances = []
    instances.append(run_cmd_async(cmds[0]))
    for cmd in cmds[1:]:
        time.sleep(20)
        instances.append(run_cmd_async(cmd))

    leader.wait()
    for instance in instances:
        instance.wait()


def retry(tries: int = 2, timeout: int = 600) -> Callable[[Callable], Callable]:
    """
    Decorator that retries an experiment `tries` times in case a run did not finished 
    in `timeout` seconds.
    """
    def _retry(f: Callable) -> Callable:
        def wrapped(*args, **kwargs):
            timed_f = timeout_func(timeout, use_signals=False)(f)
            for _ in range(tries):
                try:
                    return timed_f(*args, **kwargs)
                except TimeoutError:
                    pid = os.getpid()
                    kill_subprocess(pid, without_parent=True, sig=signal.SIGTERM) 
                    os.system(f"""
                        for pid in $(pidof -o {pid} -x python3); do
                            kill -TERM $pid
                        done
                    """)
                    max_clients = 10
                    ports = ([8000 + i for i in range(max_clients)]
                          + [4000 + i for i in range(max_clients)]
                          + [8080 + i for i in range(max_clients)])
                    for port in ports:
                        os.system(f"kill -9 $(lsof -t -i:{port})")
                    os.system("pkill -9 chrome")
                    time.sleep(20)
            raise RuntimeError("Maximum retries reached")
        return wrapped
    return _retry


def cleanup_files():
    """
    Cleanup temporary files generated by the GET_SINGLETON macro from the QUIC backend 
    implementation.
    """
    os.system("rm -f /tmp/tmp_*")


@retry(tries=2, timeout=1500)
def run_subexp(
    bandwidth: int, 
    latency: int, 
    path: str, 
    servers: List[str], 
    force_run: bool = False,
    burst: int = 20000,
    video: Optional[str] = None,
    headless: bool = False,
) -> None:
    """
    Run a list of (QUIC, Chrome) pairs over a shared `bandwidth` with a fixed `latency` 
    and `burst` for TC for video `video. The experiments can run `headless`.
    """
    cleanup_files()
    if os.path.isdir(path) and not force_run:
        return   
    
    wait_for = len(servers)
    leader_cmd = (
        f"python3 leader.py -b {bandwidth} -l {latency} --port 8800 {wait_for} --path {path} --plot --burst {burst}"
    )
    if video:
        leader_cmd += f' --video {video}'
    if headless:
        leader_cmd += " --headless"

    ports_start = 8000
    q_ports_start = 4000

    cmds = []
    for i, server in enumerate(servers):
        port = ports_start + i + 1
        q_port = q_ports_start + i + 1
        cmds.append(
            f"python3 run.py --port {port} --quic-port {q_port} -lp 8800 {server} --path {path}"
        )
        if headless:
            cmds[-1] += " --headless"
    run_cmds(leader_cmd, cmds)

@retry(tries=2, timeout=350)
def run_traffic(
    path: str, 
    server: str,
    force_run: bool = False,
    headless: bool = False,
    burst: int = 2000,
):
    """
    Run a single (QUIC, Chrome) pair over a shared `bandwidth` over a link with custom 
    background TCP traffic.
    """
    cleanup_files()
    if os.path.isdir(path) and not force_run:
        return   
    ports = "--port 8001 --quic-port 4001"
    extra = f"--burst {burst} --plot --traffic"
    cmd = (
        f"python3 run.py {ports} {server} {extra} --path {path}"
    )
    if headless:
        cmd += " --headless"
    
    instance = run_cmd_async(cmd)
    instance.wait()


@retry(tries=2, timeout=350)
def run_trace(
    path: str, 
    server: str,
    force_run: bool = False,
    headless: bool = False,
):
    """ 
    Run a single (QUIC, Chrome) pair over a variable bandwidth trace.
    """
    cleanup_files()
    if os.path.isdir(path) and not force_run:
        return   
    ports = "--port 8001 --quic-port 4001"
    extra = "--burst 2000 --plot"
    cmd = (
        f"python3 run.py {ports} {server} {extra} --path {path}"
    )
    if headless:
        cmd += " --headless"
    
    instance = run_cmd_async(cmd)
    instance.wait()
