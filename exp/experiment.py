from argparse import ArgumentParser, Namespace
from collections import defaultdict
from pathlib import Path
from subprocess import Popen
from typing import Callable, List

import os
import json
import time

import traceback


EXPERIMENTS = {}


def experiment(f: Callable[[Namespace], None]) -> Callable[[Namespace], None]:
    global EXPERIMENTS
    EXPERIMENTS[f.__name__] = f
    return f


def run_cmd(cmd: str) -> None:
    print(f'[Experiment runnner] > {cmd}') 
    os.system(cmd)


def run_cmd_async(cmd: str) -> Popen:
    print(f'[Experiment runner] > {cmd}')
    return Popen([arg for arg in cmd.split(' ') if len(arg) > 0])


@experiment
def server_overhead(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "experiment1")
    os.system(f"mkdir -p {experiment_path}")

    experiment_log = open(str(Path(experiment_path) / "log.txt"), "w")
    for bandwidth in [0.5, 1, 2, 3, 4, 5, 10, 20, 50]:
        for latency in [10, 50, 200]:
            experiment_log.write(f'> [bandwidth] {bandwidth}, [latency] {latency}: [qoe] ')
            for server in ['front_end', 'back_end']:
                path = str(Path(experiment_path) / f'{server}_{bandwidth}_{latency}')
                dash = "" if server == "back_end" else "-d fe=bb"
                cmd  = f"python3 run.py -l {latency} -b {bandwidth} {dash} --path {path}"
               
                if not os.path.isdir(path):
                    run_cmd(cmd)
                with open(str(Path(path) / 'plots.log'), 'r') as graph_log:
                    qoe = {}
                    for line in graph_log.read().split('\n'):
                        try:
                            obj = json.loads(line)
                            qoe[obj["x"]] = obj["qoe"]
                        except:
                            pass
                    del qoe[0]
                    del qoe[49]

                    qoe_vals = list(qoe.values())
                    total_qoe = sum(qoe_vals) / len(qoe_vals)
                    experiment_log.write(f'{total_qoe} ') 
            experiment_log.write('\n')


@experiment
def multiple_example(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "multiple1")
    for bandwidth in [100]:
        for latency in [10]:
            for server1 in ['back_end']:
                for server2 in ['back_end']:
                    path = str(Path(experiment_path) / f'{bandwidth}_{latency}_{server1}_{server2}')
                    
                    dash1 = "" if server1 == "back_end" else "--algo bb"
                    dash2 = "" if server2 == "back_end" else "--algo bb"

                    leader_cmd = f"python3 leader.py -b {bandwidth} -l {latency} --port 8800 2 --path {path} --plot"
                    cmd1  = f"python3 run.py --port 8000 --quic-port 4000 -lp 8800 --name a {dash1} --path {path}"
                    cmd2  = f"python3 run.py --port 8001 --quic-port 4001 -lp 8800 --name b {dash2} --path {path}"
                    
                    leader = run_cmd_async(leader_cmd)
                    time.sleep(1)
                    instance1 = run_cmd_async(cmd1)
                    time.sleep(15)
                    instance2 = run_cmd_async(cmd2)

                    leader.wait()
                    instance1.wait()
                    instance2.wait()


@experiment
def worthed_abr(args: Namespace) -> None:
    def run_cmds(leader_cmd, cmd1, cmd2):
        leader = run_cmd_async(leader_cmd)
        time.sleep(1)
        instance1 = run_cmd_async(cmd1)
        time.sleep(20)
        instance2 = run_cmd_async(cmd2)

        leader.wait()
        instance1.wait()
        instance2.wait()
    
    def run_subexp(bandwidth, latency, path, server1, server2):
        leader_cmd = (
            f"python3 leader.py -b {bandwidth} -l {latency} --port 8800 2 --path {path} --plot"
        )
        cmd1 = (
            f"python3 run.py --port 8001 --quic-port 4001 -lp 8800 {server1} --path {path}"
        )
        cmd2 = (
            f"python3 run.py --port 8002 --quic-port 4002 -lp 8800 {server2} --path {path}"
        )
        run_cmds(leader_cmd, cmd1, cmd2)

    def run_trace(path, server):
        ports = "--port 8001 --quic-port 4001"
        extra = "--burst 2000 --plot"
        cmd = (
            f"python3 run.py {ports} {server} {extra} --path {path}"
        )
        instance = run_cmd_async(cmd)
        instance.wait()

    paths = []
    experiment_path = str(Path("experiments") / "worthed_abr")
    os.system(f"mkdir -p {experiment_path}")

    for bandwidth in [3, 2, 1]:
        for latency in [10]:
            # pensieve vs worthed abr
            subpath = str(Path(experiment_path) / "versus_pensieve")
            for cc in ['cubic', 'bbr']:
                server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                server2 = "--server-algo worthed --name abrcc --cc abbr"
                
                path = str(Path(subpath) / f"{cc}_{bandwidth}_{latency}")
                run_subexp(bandwidth, latency, path, server1, server2)
                paths.append(str(Path(path) / "leader_plots.log"))

            # self
            subpath = str(Path(experiment_path) / "versus_self")
            server1 = "--server-algo worthed --name abrcc1 --cc abbr"
            server2 = "--server-algo worthed --name abrcc2 --cc abbr"
            
            path = str(Path(subpath) / f"{bandwidth}_{latency}")
            run_subexp(bandwidth, latency, path, server1, server2)
            paths.append(str(Path(path) / "leader_plots.log"))
    
            # pensieve vs pensieve
            subpath = str(Path(experiment_path) / "pensieve")
            for cc1, cc2 in [('cubic', 'bbr'), ('cubic', 'cubic'), ('bbr', 'bbr')]:
                server1 = f"--algo pensieve --name pensieve1 --cc {cc1}" 
                server2 = f"--algo pensieve --name pensieve2 --cc {cc2}"

                path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_{latency}")
                run_subexp(bandwidth, latency, path, server1, server2)
                paths.append(str(Path(path) / "leader_plots.log"))
    
    # traces
    for latency in [10]:
        server1 = "--cc abbr --server-algo worthed --name abrcc"
        server2 = "--cc bbr --algo pensieve --name pensieve"
        for name, server in [("abrcc", server1), ("pensieve", server2)]:
            traces = Path("network_traces")
            for trace in [str(traces / "bus1.txt"), str(traces / "norway_train_6.txt")]:
                trace_name = trace.split('/')[-1].split('.')[0]
                path = str(Path(experiment_path) / f'{name}_{trace_name}_{latency}')
                run_trace(path, f"{server} -l {latency} -t {trace}")
                paths.append(str(Path(path) / f"{name}_plots.log"))
    
    # summary
    experiment_log = open(str(Path(experiment_path) / "log.txt"), "w")
    for path in paths:
        try:
            with open(path, 'r') as graph_log:
                raw_qoe = defaultdict(lambda: defaultdict(int))
                vmaf_qoe = defaultdict(lambda: defaultdict(int))
                
                for line in graph_log.read().split('\n'):
                    def proc_metric(curr_dict, metric):
                        if metric not in obj:
                            return
                        x = obj['x']
                        for name, value in obj[metric].items():
                            # not great
                            if x != 0 and x != 49:
                                curr_dict[name][x] = value
                    
                    try:
                        obj = json.loads(line)
                    except:
                        pass
                    proc_metric(raw_qoe, "raw_qoe")
                    proc_metric(vmaf_qoe, "vmaf_qoe")

                for name in raw_qoe.keys():
                    qoe_vals = list(raw_qoe[name].values())
                    total_qoe = sum(qoe_vals) / len(qoe_vals)

                    vmaf_vals = list(vmaf_qoe[name].values())
                    total_vmaf = sum(vmaf_vals)
                    
                    experiment_log.write(
                        f'> [{path}] {name}: raw qoe {total_qoe}; vmaf qoe {total_vmaf}'
                    )
                    experiment_log.write('\n')
        except FileNotFoundError as e:
            pass


if __name__ == "__main__":
    parser = ArgumentParser(description=
        f'Run experiment setup in this Python file. ' +
        f'Available experiments: {list(EXPERIMENTS.keys())}')
    parser.add_argument('name', type=str, help='Experiment name.')
    args = parser.parse_args()

    if args.name in EXPERIMENTS:
        EXPERIMENTS[args.name](args)
    else:
        print(f'No such experiment: {args.name}')
        print(f'Available experiments: {list(EXPERIMENTS.keys())}')
