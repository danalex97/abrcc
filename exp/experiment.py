from argparse import ArgumentParser, Namespace
from pathlib import Path

from exp_util.env import experiment, experiments, run_subexp, run_trace
from exp_util.data import Experiment, save_experiments, generate_summary, load_experiments
from exp_util.plot import plot_bar, plot_cdf

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

    for run_id in range(5):
        for bandwidth in [4, 3, 2, 1]:
            for latency in [500]:
                # pensieve vs worthed abr
                subpath = str(Path(experiment_path) / "versus_pensieve")
                for cc in ['cubic', 'bbr']:
                    server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                    server2 = "--server-algo worthed --name abrcc --cc abbr"
                    
                    path = str(Path(subpath) / f"{cc}_{bandwidth}_{latency}_run{run_id}")
                    run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                    experiments.append(Experiment(
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["versus", "pensieve", cc, "worthed"],
                        run_id = run_id,
                    ))
                

                # self
                subpath = str(Path(experiment_path) / "versus_self")
                server1 = "--server-algo worthed --name abrcc1 --cc abbr"
                server2 = "--server-algo worthed --name abrcc2 --cc abbr"
                
                path = str(Path(subpath) / f"{bandwidth}_{latency}_run{run_id}")
                run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                experiments.append(Experiment(
                    path = str(Path(path) / "leader_plots.log"),
                    latency = latency,
                    bandwidth = bandwidth,
                    extra = ["self", "worthed"],
                    run_id = run_id,
                ))
        
                # pensieve vs pensieve
                subpath = str(Path(experiment_path) / "pensieve")
                for cc1, cc2 in [('cubic', 'bbr'), ('cubic', 'cubic'), ('bbr', 'bbr')]:
                    server1 = f"--algo pensieve --name pensieve1 --cc {cc1}" 
                    server2 = f"--algo pensieve --name pensieve2 --cc {cc2}"

                    path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_{latency}_run{run_id}")
                    run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                    experiments.append(Experiment(
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["pensieve", "alone", f"{cc1}_{cc2}"],
                        run_id = run_id,
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
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    experiments = []
    experiment_path = str(Path("experiments") / "target_abr")
    os.system(f"mkdir -p {experiment_path}")
    runner_log = open(str(Path(experiment_path) / 'exp.log'), 'w')
    
    for run_id in range(5):
        for bandwidth in [4, 3, 2, 1]:
            for latency in [500]:
                # pensieve vs worthed abr
                subpath = str(Path(experiment_path) / "versus_pensieve")
                for cc in ['cubic', 'bbr']:
                    for adapt in ['abbr', 'xbbr']:
                        server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                        server2 = f"--server-algo target --name abrcc --cc {adapt}"
                        
                        path = str(Path(subpath) / f"{cc}_{adapt}_{bandwidth}_{latency}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                        experiments.append(Experiment(
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = ["versus", "pensieve", cc, adapt, "target"],
                            run_id = run_id,
                        ))
                
                # self
                for adapt in ['abbr', 'xbbr']:
                    subpath = str(Path(experiment_path) / "versus_self")
                    server1 = f"--server-algo target --name abrcc1 --cc {adapt}"
                    server2 = f"--server-algo target --name abrcc2 --cc {adapt}"
                    
                    path = str(Path(subpath) / f"{adapt}_{bandwidth}_{latency}_run{run_id}")
                    runner_log.write(f'> {path}\n')
                    run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                    experiments.append(Experiment(
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["self", "target", adapt],
                        run_id = run_id,
                    ))

        # traces
        subpath = str(Path(experiment_path) / "traces")
        for latency in [500]:
            server0 = "--cc xbbr --server-algo target --name abrcc_xbbr"
            server1 = "--cc abbr --server-algo target --name abrcc"
            server2 = "--cc bbr --algo pensieve --name pensieve"
            for name, server in [("pensieve", server2), ("abrcc", server1), ("abrcc_xbbr", server0)]:
                traces = Path("network_traces")
                for trace in [str(traces / "bus1.txt"), str(traces / "norway_train_6.txt")]:
                    trace_name = trace.split('/')[-1].split('.')[0]
                    path = str(Path(subpath) / f'{name}_{trace_name}_{latency}_run{run_id}')
                    runner_log.write(f'> {path}\n')
                    run_trace(path, f"{server} -l {latency} -t {trace}")
                    experiments.append(Experiment(
                        path = str(Path(path) / f"{name}_plots.log"),
                        latency = latency,
                        trace = trace,
                        extra = ["traces", "target", trace],
                        run_id = run_id,
                    ))
   
    if args.dry:
        print(experiments)
    else:
        save_experiments(experiment_path, experiments)
        generate_summary(experiment_path, experiments)


@experiment
def traces(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    experiments = []
    experiment_path = str(Path("experiments") / "traces")
    os.system(f"mkdir -p {experiment_path}")
    runner_log = open(str(Path(experiment_path) / 'exp.log'), 'w')
    
    # traces
    subpath = Path(experiment_path)
    for latency in [500]:
        server0 = "--cc xbbr --server-algo target --name target_xbbr"
        server1 = "--cc abbr --server-algo target --name target"
        server2 = "--cc bbr --algo pensieve --name pensieve_bbr"
        server3 = "--cc cubic --algo pensieve --name pensieve_cubic"
        server4 = "--cc abbr --server-algo worthed --name worthed"
        for name, server in [
            ("target_xbbr", server0),
            ("target", server1), 
            ("pensieve_bbr", server2), 
            ("pensieve_cubic", server3), 
            ("worthed", server4), 
        ]:
            traces = Path("network_traces")
            for trace in [
                str(traces / "car.txt"), 
                str(traces / "bus.txt"), 
                str(traces / "bus1.txt"), 
                
                str(traces / "norway_train_6.txt"),
                str(traces / "norway_train_13.txt"),

                str(traces / "norway_ferry_11.txt"), 
                str(traces / "norway_ferry_20.txt"),
                str(traces / "norway_ferry_6.txt"),
                
                str(traces / "norway_metro_6.txt"),
                str(traces / "norway_tram_5.txt"),
                str(traces / "norway_tram_14.txt"),
                
                str(traces / "norway_tram_16.txt"),
                str(traces / "norway_tram_19.txt"),
            ]:
                trace_name = trace.split('/')[-1].split('.')[0]
                path = str(Path(subpath) / f'{name}_{trace_name}_{latency}')
                runner_log.write(f'> {path}\n')
                run_trace(path, f"{server} -l {latency} -t {trace}")
                experiments.append(Experiment(
                    path = str(Path(path) / f"{name}_plots.log"),
                    latency = latency,
                    trace = trace,
                    extra = ["traces", name, trace],
                ))
   
    if args.dry:
        print(len(experiments))
    else:
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
        (["versus", "pensieve", "cubic", "target", "abbr"], ("abrcc", "target") ),
        (["versus", "pensieve", "cubic", "target", "xbbr"], ("abrcc", "xtarget") ),
        (["alone", "pensieve", "cubic_cubic"], (max, "pensieve_cubic") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve2", "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "performance_versus_bbr"), experiments, [
        (["versus", "pensieve", "bbr", "worthed"], ("abrcc", "worthed") ),
        (["versus", "pensieve", "bbr", "target", "abbr"], ("abrcc", "target") ),
        (["versus", "pensieve", "bbr", "target", "xbbr"], ("abrcc", "xtarget") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve1", "pensieve_cubic") ),
        (["alone", "pensieve", "bbr_bbr"], (max, "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "fairness_versus_cubic"), experiments, [
        (["versus", "pensieve", "cubic", "worthed"], ("pensieve", "worthed") ),
        (["versus", "pensieve", "cubic", "target", "abbr"], ("pensieve", "target") ),
        (["versus", "pensieve", "cubic", "target", "xbbr"], ("pensieve", "xtarget") ),
        (["alone", "pensieve", "cubic_cubic"], (min, "pensieve_cubic") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve1", "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "fairness_versus_bbr"), experiments, [
        (["versus", "pensieve", "bbr", "worthed"], ("pensieve", "worthed") ),
        (["versus", "pensieve", "bbr", "target", "abbr"], ("pensieve", "target") ),
        (["versus", "pensieve", "bbr", "target", "xbbr"], ("pensieve", "xtarget") ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve2", "pensieve_cubic") ),
        (["alone", "pensieve", "bbr_bbr"], (min, "pensieve_bbr") ),
    ])
    plot_bar(str(Path(experiment_path) / "performance_self"), experiments, [
        (["self", "target", "abbr"], (min, "target") ),
        (["self", "target", "xbbr"], (min, "xtarget") ),
        (["self", "worthed"], (min, "worthed") ),
        (["alone", "pensieve", "cubic_cubic"], (min, "pensieve_cubic") ),
        (["alone", "pensieve", "bbr_bbr"], (min, "pensieve_bbr") ),
    ])
    traces = Path("network_traces")
    plot_bar(str(Path(experiment_path) / "performance_bus_1"), experiments, [
        (["traces", "target", str(traces / "bus1.txt")], ("abrcc", "target") ),
        (["traces", "target", str(traces / "bus1.txt")], ("abrcc_xbbr", "xtarget") ),
        (["traces", "worthed", str(traces / "bus1.txt")], ("abrcc", "worthed") ),
        (["traces", "target", str(traces / "bus1.txt")], ("pensieve", "pensieve") ),
    ])
    plot_bar(str(Path(experiment_path) / "performance_norway_train_6"), experiments, [
        (["traces", "target", str(traces / "norway_train_6.txt")], ("abrcc", "target") ),
        (["traces", "target", str(traces / "norway_train_6.txt")], ("abrcc_xbbr", "xtarget") ),
        (["traces", "worthed", str(traces / "norway_train_6.txt")], ("abrcc", "worthed") ),
        (["traces", "target", str(traces / "norway_train_6.txt")], ("pensieve", "pensieve") ),
    ])


@experiment
def plot_traces(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "plots")
    os.system(f"mkdir -p {experiment_path}")
    
    experiments = sum([load_experiments(experiment) for experiment in [
       str(Path("experiments") / "traces")
    ]], [])

    plot_cdf(str(Path(experiment_path) / "traces"), experiments, [
        (["traces", "target_xbbr"], ("target_xbbr", "xtarget") ),
        (["traces", "target"], ("target", "target") ),
        (["traces", "pensieve_bbr"], ("pensieve_bbr", "pensieve_bbr") ),
        (["traces", "pensieve_cubic"], ("pensieve_cubic", "pensieve_cubic") ),
        (["traces", "worthed"], ("worthed", "worthed") ),
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
            for cc in ['cubic', 'bbr']:
                server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                server2 = "--server-algo target --name abrcc --cc xbbr"
                
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
    parser.add_argument('-d', '--dry', action='store_true', dest='dry', help='Dry run.')
    args = parser.parse_args()

    if args.name in experiments():
        experiments()[args.name](args)
    else:
        print(f'No such experiment: {args.name}')
        print(f'Available experiments: {list(EXPERIMENTS.keys())}')
