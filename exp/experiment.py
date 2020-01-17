from argparse import ArgumentParser, Namespace
from pathlib import Path
from subprocess import Popen
from typing import Callable, List

import os
import json
import time


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
def experiment1(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "experiment1")
    os.system(f"mkdir -p {experiment_path}")

    experiment_log = open(str(Path(experiment_path) / "log.txt"), "w")
    for bandwidth in [0.5, 1, 2, 3, 4, 5, 10, 20, 50]:
        for latency in [10, 50, 200]:
            experiment_log.write(f'> [bandwidth] {bandwidth}, [latency] {latency}: [qoe] ')
            for server in ['front_end', 'back_end']:
                path = str(Path(experiment_path) / f'{server}_{bandwidth}_{latency}')
                dash = "" if server == "back_end" else "-d fe"
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
def multiple1(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "multiple1")
    for bandwidth in [200]:
        for latency in [10]:
            for server1 in ['back_end']:
                for server2 in ['front_end']:
                    path = str(Path(experiment_path) / f'{bandwidth}_{latency}_{server1}_{server2}')
                    
                    dash1 = "" if server1 == "back_end" else "-d fe"
                    dash2 = "" if server2 == "back_end" else "-d fe"

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
