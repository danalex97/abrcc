from argparse import ArgumentParser, Namespace
from pathlib import Path

from exp_util.env import experiment, experiments, run_subexp, run_trace
from exp_util.data import Experiment, save_experiments, generate_summary, load_experiments
from exp_util.plot import plot_bar

import os
import time


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
    experiments = []
    experiment_path = str(Path("experiments") / "worthed_abr")
    os.system(f"mkdir -p {experiment_path}")

    for bandwidth in [3, 2, 1]:
        for latency in [500]:
            # pensieve vs worthed abr
            subpath = str(Path(experiment_path) / "versus_pensieve")
            for cc in ['cubic', 'bbr']:
                server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                server2 = "--server-algo worthed --name abrcc --cc abbr"
                
                path = str(Path(subpath) / f"{cc}_{bandwidth}_{latency}")
                run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                experiments.append(Experiment(
                    path = str(Path(path) / "leader_plots.log"),
                    latency = latency,
                    bandwidth = bandwidth,
                    extra = ["versus", "pensieve", cc, "worthed"],
                ))
            

            # self
            subpath = str(Path(experiment_path) / "versus_self")
            server1 = "--server-algo worthed --name abrcc1 --cc abbr"
            server2 = "--server-algo worthed --name abrcc2 --cc abbr"
            
            path = str(Path(subpath) / f"{bandwidth}_{latency}")
            run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
            experiments.append(Experiment(
                path = str(Path(path) / "leader_plots.log"),
                latency = latency,
                bandwidth = bandwidth,
                extra = ["self", "worthed"],
            ))
    
            # pensieve vs pensieve
            subpath = str(Path(experiment_path) / "pensieve")
            for cc1, cc2 in [('cubic', 'bbr'), ('cubic', 'cubic'), ('bbr', 'bbr')]:
                server1 = f"--algo pensieve --name pensieve1 --cc {cc1}" 
                server2 = f"--algo pensieve --name pensieve2 --cc {cc2}"

                path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_{latency}")
                run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                experiments.append(Experiment(
                    path = str(Path(path) / "leader_plots.log"),
                    latency = latency,
                    bandwidth = bandwidth,
                    extra = ["pensieve", "alone", f"{cc1}_{cc2}"],
                ))
            
    
    # traces
    subpath = str(Path(experiment_path) / "traces")
    for latency in [500]:
        server1 = "--cc abbr --server-algo worthed --name abrcc"
        server2 = "--cc bbr --algo pensieve --name pensieve"
        for name, server in [("abrcc", server1), ("pensieve", server2)]:
            traces = Path("network_traces")
            for trace in [str(traces / "bus1.txt"), str(traces / "norway_train_6.txt")]:
                trace_name = trace.split('/')[-1].split('.')[0]
                path = str(Path(subpath) / f'{name}_{trace_name}_{latency}')
                run_trace(path, f"{server} -l {latency} -t {trace}")
                experiments.append(Experiment(
                    path = str(Path(path) / f"{name}_plots.log"),
                    latency = latency,
                    trace = trace,
                    extra = ["traces", "worthed", trace],
                ))
    
    save_experiments(experiment_path, experiments)
    generate_summary(experiment_path, experiments)


@experiment
def target_abr(args: Namespace) -> None:
    experiments = []
    experiment_path = str(Path("experiments") / "target_abr")
    os.system(f"mkdir -p {experiment_path}")
    
    for bandwidth in [3, 2, 1]:
        for latency in [500]:
            # pensieve vs worthed abr
            subpath = str(Path(experiment_path) / "versus_pensieve")
            for cc in ['cubic', 'bbr']:
                server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                server2 = "--server-algo target --name abrcc --cc abbr"
                
                path = str(Path(subpath) / f"{cc}_{bandwidth}_{latency}")
                run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                experiments.append(Experiment(
                    path = str(Path(path) / "leader_plots.log"),
                    latency = latency,
                    bandwidth = bandwidth,
                    extra = ["versus", "pensieve", cc, "target"],
                ))
            
            # self
            subpath = str(Path(experiment_path) / "versus_self")
            server1 = "--server-algo target --name abrcc1 --cc abbr"
            server2 = "--server-algo target --name abrcc2 --cc abbr"
            
            path = str(Path(subpath) / f"{bandwidth}_{latency}")
            run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
            experiments.append(Experiment(
                path = str(Path(path) / "leader_plots.log"),
                latency = latency,
                bandwidth = bandwidth,
                extra = ["self", "target"],
            ))

    # traces
    subpath = str(Path(experiment_path) / "traces")
    for latency in [500]:
        server1 = "--cc abbr --server-algo target --name abrcc"
        server2 = "--cc bbr --algo pensieve --name pensieve"
        for name, server in [("abrcc", server1), ("pensieve", server2)]:
            traces = Path("network_traces")
            for trace in [str(traces / "bus1.txt"), str(traces / "norway_train_6.txt")]:
                trace_name = trace.split('/')[-1].split('.')[0]
                path = str(Path(subpath) / f'{name}_{trace_name}_{latency}')
                run_trace(path, f"{server} -l {latency} -t {trace}")
                experiments.append(Experiment(
                    path = str(Path(path) / f"{name}_plots.log"),
                    latency = latency,
                    trace = trace,
                    extra = ["traces", "target", trace],
                ))
    
    save_experiments(experiment_path, experiments)
    generate_summary(experiment_path, experiments)


@experiment
def generate_plots(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "plots")
    os.system(f"mkdir -p {experiment_path}")
    
    experiments = sum([load_experiments(experiment) for experiment in [
       str(Path("experiments") / "target_abr"),
       str(Path("experiments") / "worthed_abr")
    ]], [])
    plot_bar(str(Path(experiment_path) / "performance_versus_cubic"), experiments, [
        (["versus", "pensieve", "cubic", "worthed"], ("abrcc", "worthed") ),
        (["versus", "pensieve", "cubic", "target"], ("abrcc", "target") ),
        (["alone", "pensieve", "cubic_cubic"], (max, "pensieve_cubic") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve2", "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "performance_versus_bbr"), experiments, [
        (["versus", "pensieve", "bbr", "worthed"], ("abrcc", "worthed") ),
        (["versus", "pensieve", "bbr", "target"], ("abrcc", "target") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve1", "pensieve_cubic") ),
        (["alone", "pensieve", "bbr_bbr"], (max, "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "fairness_versus_cubic"), experiments, [
        (["versus", "pensieve", "cubic", "worthed"], ("pensieve", "worthed") ),
        (["versus", "pensieve", "cubic", "target"], ("pensieve", "target") ),
        (["alone", "pensieve", "cubic_cubic"], (min, "pensieve_cubic") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve1", "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "fairness_versus_bbr"), experiments, [
        (["versus", "pensieve", "bbr", "worthed"], ("pensieve", "worthed") ),
        (["versus", "pensieve", "bbr", "target"], ("pensieve", "target") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve2", "pensieve_cubic") ),
        (["alone", "pensieve", "bbr_bbr"], (min, "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "performance_self"), experiments, [
        (["self", "target"], (min, "target") ),
        (["self", "worthed"], (min, "worthed") ),
        (["alone", "pensieve", "cubic_cubic"], (min, "pensieve_cubic") ),
        (["alone", "pensieve", "bbr_bbr"], (min, "pensieve_bbr") ),
    ])
    traces = Path("network_traces")
    plot_bar(str(Path(experiment_path) / "performance_bus_1"), experiments, [
        (["traces", "target", str(traces / "bus1.txt")], ("abrcc", "target") ),
        (["traces", "worthed", str(traces / "bus1.txt")], ("abrcc", "worthed") ),
        (["traces", "target", str(traces / "bus1.txt")], ("pensieve", "pensieve") ),
    ])
    plot_bar(str(Path(experiment_path) / "performance_norway_train_6"), experiments, [
        (["traces", "target", str(traces / "norway_train_6.txt")], ("abrcc", "target") ),
        (["traces", "worthed", str(traces / "norway_train_6.txt")], ("abrcc", "worthed") ),
        (["traces", "target", str(traces / "norway_train_6.txt")], ("pensieve", "pensieve") ),
    ])


@experiment
def test(args: Namespace) -> None:
    experiments = []
    experiment_path = str(Path("experiments") / "test")
    os.system(f"mkdir -p {experiment_path}")
    
    for bandwidth in [3, 2, 1]:
        for latency in [500]:
            # pensieve vs worthed abr
            subpath = str(Path(experiment_path) / "versus_pensieve")
            for cc in ['bbr', 'cubic']:
                server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                server2 = "--server-algo target --name abrcc --cc abbr"
                
                path = str(Path(subpath) / f"{cc}_{bandwidth}_{latency}")
                run_subexp(bandwidth, latency, path, server1, server2, burst=2000, force_run=True)
                experiments.append(Experiment(
                    path = str(Path(path) / "leader_plots.log"),
                    latency = latency,
                    bandwidth = bandwidth,
                    extra = ["versus", "pensieve", cc, "target"],
                ))
 

if __name__ == "__main__":
    parser = ArgumentParser(description=
        f'Run experiment setup in this Python file. ' +
        f'Available experiments: {list(experiments().keys())}')
    parser.add_argument('name', type=str, help='Experiment name.')
    args = parser.parse_args()

    if args.name in experiments():
        experiments()[args.name](args)
    else:
        print(f'No such experiment: {args.name}')
        print(f'Available experiments: {list(EXPERIMENTS.keys())}')
