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
def multiple(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    videos = ['maca', 'got', 'bojack', 'guard', 'cook']

    experiments = []
    root_path = str(Path("experiments") / "multiple_videos")
    os.system(f"mkdir -p {root_path}")
    runner_log = open(str(Path(root_path) / 'exp.log'), 'w')
   
    compete1 = [
        ('robustMpc', 'cubic'),
        ('robustMpc', 'bbr'),
    ]
    compete2 = [
        ('target', 'abbr'), 
        ('target', 'xbbr'), 
        ('target2', 'target')
    ]

    for video in videos:
        experiment_path = str(Path(root_path) / video)
        for run_id in [0]:
            latency = 500
            for bandwidth in [3, 2, 1]:
                # robustMpc vs Target, xTarget, Target2 
                subpath = str(Path(experiment_path) / "versus_rmpc")
                for (algo1, cc1) in compete1:
                    for (algo2, cc2) in compete2:
                        server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video}" 
                        server2 = f"--server-algo {algo2} --name abrcc --cc {cc2} --video {video}"
                        
                        path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        
                        run_subexp(bandwidth, latency, path, server1, server2, burst=2000, video=video)
                        experiments.append(Experiment(
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = ["versus", cc1, algo2, cc2],
                            run_id = run_id,
                        ))
                
                # self
                subpath = str(Path(experiment_path) / "versus_self")
                for (algo, cc) in compete2:
                    server1 = f"--server-algo {algo} --name abrcc1 --cc {cc} --video {video}"
                    server2 = f"--server-algo {algo} --name abrcc2 --cc {cc} --video {video}"
                    
                    path = str(Path(subpath) / f"{cc}_{bandwidth}_run{run_id}")
                    runner_log.write(f'> {path}\n')
                    run_subexp(bandwidth, latency, path, server1, server2, burst=2000, video=video)
                    experiments.append(Experiment(
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["self", algo, cc],
                        run_id = run_id,
                    ))

                # robustMpc
                subpath = str(Path(experiment_path) / "rmpc")
                for (algo, cc) in compete2:
                    server1 = f"--algo {algo} --name abrcc1 --cc {cc} --video {video}"
                    server2 = f"--algo {algo} --name abrcc2 --cc {cc} --video {video}"
                    
                    path = str(Path(subpath) / f"{cc}_{bandwidth}_run{run_id}")
                    runner_log.write(f'> {path}\n')
                    run_subexp(bandwidth, latency, path, server1, server2, burst=2000, video=video)
                    experiments.append(Experiment(
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["self", algo, cc],
                        run_id = run_id,
                    ))

        # traces
        subpath = str(Path(experiment_path) / "traces")
        server0 = "--cc xbbr --server-algo target --name abrcc"
        server1 = "--cc abbr --server-algo target --name abrcc"
        server2 = "--cc target --server-algo target2 --name abrcc"
        server3 = "--cc bbr --algo robustMpc --name robustMpc"
        for name, server in [
            ("robustMpc", server3), 
            ("target", server1), 
            ("target2", server2),
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
                path = str(Path(subpath) / f'{name}_{trace_name}')
                runner_log.write(f'> {path}\n')
                run_trace(path, f"{server} -l {latency} -t {trace}")
                experiments.append(Experiment(
                    path = str(Path(path) / f"{name}_plots.log"),
                    latency = latency,
                    trace = trace,
                    extra = ["traces", name, trace, run_id],
                    run_id = run_id,
                ))

    if args.dry:
        print(experiments)
        print(len(experiments))
    else:
        save_experiments(experiment_path, experiments)
        generate_summary(experiment_path, experiments)



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
        for bandwidth in [3, 2, 1]:
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
        for bandwidth in [3, 2, 1]:
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
def target_abr2(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    experiments = []
    experiment_path = str(Path("experiments") / "target_abr2")
    os.system(f"mkdir -p {experiment_path}")
    runner_log = open(str(Path(experiment_path) / 'exp.log'), 'w')
    
    for run_id in range(1):
        for bandwidth in [3, 2, 1]:
            for latency in [500]:
                # pensieve vs target
                subpath = str(Path(experiment_path) / "versus_pensieve")
                for cc in ['cubic', 'bbr']:
                    for adapt in ['target']:
                        server1 = f"--algo pensieve --name pensieve --cc {cc}" 
                        server2 = f"--server-algo target2 --name abrcc --cc {adapt}"
                        
                        path = str(Path(subpath) / f"{cc}_{adapt}_{bandwidth}_{latency}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                        experiments.append(Experiment(
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = ["versus", "pensieve", cc, "target2"],
                            run_id = run_id,
                        ))
                
                # self
                for adapt in ['target']:
                    subpath = str(Path(experiment_path) / "versus_self")
                    server1 = f"--server-algo target2 --name abrcc1 --cc {adapt}"
                    server2 = f"--server-algo target2 --name abrcc2 --cc {adapt}"
                    
                    path = str(Path(subpath) / f"{adapt}_{bandwidth}_{latency}_run{run_id}")
                    runner_log.write(f'> {path}\n')
                    run_subexp(bandwidth, latency, path, server1, server2, burst=2000)
                    experiments.append(Experiment(
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["self", "target2"],
                        run_id = run_id,
                    ))

        # traces
        subpath = str(Path(experiment_path) / "traces")
        for latency in [500]:
            server1 = "--cc target --server-algo target2 --name abrcc"
            for name, server in [("abrcc", server1)]:
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
                        extra = ["traces", "target2", trace],
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
       str(Path("experiments") / "worthed_abr"),
       str(Path("experiments") / "target_abr2")
    ]], [])
    plot_bar(str(Path(experiment_path) / "versus_cubic"), experiments, [
        # performance
        (["versus", "pensieve", "cubic", "worthed"], ("abrcc", "worthed", 1) ),
        (["versus", "pensieve", "cubic", "target", "abbr"], ("abrcc", "target", 1) ),
        (["versus", "pensieve", "cubic", "target2"], ("abrcc", "target2", 1) ),
        #(["versus", "pensieve", "cubic", "target", "xbbr"], ("abrcc", "xtarget", 1) ),
        (["alone", "pensieve", "cubic_cubic"], (max, "pensieve_cubic", 1) ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve2", "pensieve_bbr", 1) ),
    
        # fairness
        (["versus", "pensieve", "cubic", "worthed"], ("pensieve", "worthed", 2) ),
        (["versus", "pensieve", "cubic", "target", "abbr"], ("pensieve", "target", 2) ),
        (["versus", "pensieve", "cubic", "target2"], ("pensieve", "target2", 2) ),
        #(["versus", "pensieve", "cubic", "target", "xbbr"], ("pensieve", "xtarget", 2) ),
        (["alone", "pensieve", "cubic_cubic"], (min, "pensieve_cubic", 2) ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve1", "pensieve_bbr", 2) ),
    ])
    plot_bar(str(Path(experiment_path) / "versus_bbr"), experiments, [
        # performance
        (["versus", "pensieve", "bbr", "worthed"], ("abrcc", "worthed", 1) ),
        (["versus", "pensieve", "bbr", "target", "abbr"], ("abrcc", "target", 1) ),
        (["versus", "pensieve", "bbr", "target2"], ("abrcc", "target2", 1) ),
        #(["versus", "pensieve", "bbr", "target", "xbbr"], ("abrcc", "xtarget", 1) ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve1", "pensieve_cubic", 1) ),
        (["alone", "pensieve", "bbr_bbr"], (max, "pensieve_bbr", 1) ),
        
        # fairness
        (["versus", "pensieve", "bbr", "worthed"], ("pensieve", "worthed", 2) ),
        (["versus", "pensieve", "bbr", "target", "abbr"], ("pensieve", "target", 2) ),
        (["versus", "pensieve", "bbr", "target2"], ("pensieve", "target2", 2) ),
        #(["versus", "pensieve", "bbr", "target", "xbbr"], ("pensieve", "xtarget", 2) ),
        (["alone", "pensieve", "cubic_bbr"], ("pensieve2", "pensieve_cubic", 2) ),
        (["alone", "pensieve", "bbr_bbr"], (min, "pensieve_bbr", 2) ),
    ])

    plot_bar(str(Path(experiment_path) / "performance_self"), experiments, [
        (["self", "target", "abbr"], (min, "target", 1) ),
        # (["self", "target", "xbbr"], (min, "xtarget", 1) ),
        (["self", "target2"], (min, "target2", 1) ),
        (["self", "worthed"], (min, "worthed", 1) ),
        (["alone", "pensieve", "cubic_cubic"], (min, "pensieve_cubic", 1) ),
        (["alone", "pensieve", "bbr_bbr"], (min, "pensieve_bbr", 1) ),
    ])


@experiment
def plot_traces(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "plots")
    os.system(f"mkdir -p {experiment_path}")
    
    experiments = sum([load_experiments(experiment) for experiment in [
       str(Path("experiments") / "traces")
    ]], [])

    plot_cdf(str(Path(experiment_path) / "traces"), experiments, [
        #(["traces", "target_xbbr"], ("target_xbbr", "xtarget", 1) ),
        #(["traces", "target"], ("target", "target", 1) ),
        (["traces", "pensieve_bbr"], ("pensieve_bbr", "pensieve_bbr", 1) ),
        (["traces", "pensieve_cubic"], ("pensieve_cubic", "pensieve_cubic", 1) ),
        (["traces", "worthed"], ("worthed", "worthed", 1) ),
    ])


@experiment
def test(args: Namespace) -> None:
    experiments = []
    experiment_path = str(Path("experiments") / "test")
    os.system(f"mkdir -p {experiment_path}")
    
    for bandwidth in [2]:
        for latency in [200]:
            # pensieve vs worthed abr
            subpath = str(Path(experiment_path) / "versus_pensieve")
            for cc in ['bbr']:
                video = 'guard'
                server1 = f"--server-algo target2 --name target --cc target --video {video}"
                #server1 = f"--algo robustMpc --name rmpc2 --cc {cc} --video {video}"
                server2 = f"--algo robustMpc --name rmpc --cc {cc} --video {video}" 
                
                path = str(Path(subpath) / f"{cc}_{bandwidth}_{latency}")
                run_subexp(bandwidth, latency, path, server1, server2, burst=2000, force_run=True, video=video)
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
