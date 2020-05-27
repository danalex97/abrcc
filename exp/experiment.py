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
def test(args: Namespace) -> None:
    # videos = ['bojack']
    # videos = ['got']
    # videos = ['cook']
    videos = ['guard']

    experiments = []
    root_path = str(Path("test"))
    os.system(f"mkdir -p {root_path}")
   
    compete1 = [
        # ('robustMpc', 'cubic'),
        ('robustMpc', 'bbr'),
    ]
    compete2 = [
        # ('target', 'abbr'), 
        # ('target', 'xbbr'), 
        # ('target2', 'target')
        ('gap', 'gap')
        # ('target3', 'target')
    ]

    for video in videos:
        experiment_path = str(Path(root_path) / video)
        for run_id in [1]:
            latency = 500
            for bandwidth in [2]:
                # robustMpc vs Target, xTarget, Target2 
                subpath = str(Path(experiment_path) / "versus_rmpc")
                for (algo1, cc1) in compete1:
                    for (algo2, cc2) in compete2:
                        server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video}" 
                        server2 = f"--algo {algo1} --name robustMpc2 --cc {cc1} --video {video}" 
                        # server2 = f"--server-algo {algo2} --name abrcc --cc {cc2} --video {video}"
                        
                        path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        run_subexp(bandwidth, latency, path, server1, server2, burst=2000, video=video, force_run=True)


@experiment
def multiple(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    # videos = ['maca', 'got', 'bojack', 'guard', 'cook']
    videos = ['got', 'bojack', 'cook', 'guard']

    root_path = str(Path("experiments") / "multiple_videos")
    os.system(f"mkdir -p {root_path}")
    runner_log = open(str(Path(root_path) / 'exp.log'), 'w')
   
    compete1 = [
        ('robustMpc', 'cubic'),
        ('robustMpc', 'bbr'),
    ]
    compete2 = [
        ('target2', 'target'),
        ('gap', 'target'),
        ('gap', 'gap'),
    ]

    for video in videos:
        experiments = []
        experiment_path = str(Path(root_path) / video)
        for run_id in range(4):
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
                            video = video,
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = ["versus", cc1, algo2, cc2, video],
                            run_id = run_id,
                        ))

                # self
                subpath = str(Path(experiment_path) / "versus_self")
                for (algo, cc) in compete2:
                    server1 = f"--server-algo {algo} --name abrcc1 --cc {cc} --video {video}"
                    server2 = f"--server-algo {algo} --name abrcc2 --cc {cc} --video {video}"
                    
                    path = str(Path(subpath) / f"{algo}_{cc}_{bandwidth}_run{run_id}")
                    runner_log.write(f'> {path}\n')
                    run_subexp(bandwidth, latency, path, server1, server2, burst=2000, video=video)
                    experiments.append(Experiment(
                        video = video,
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["self", algo, cc],
                        run_id = run_id,
                    ))
                
                # robustMpc
                subpath = str(Path(experiment_path) / "rmpc")
                for cc1, cc2 in [('cubic', 'bbr'), ('bbr', 'bbr'), ('cubic', 'cubic')]:
                    server1 = f"--algo robustMpc --name rmpc1 --cc {cc1} --video {video}"
                    server2 = f"--algo robustMpc --name rmpc2 --cc {cc2} --video {video}"
                    
                    path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_run{run_id}")
                    runner_log.write(f'> {path}\n')
                    run_subexp(
                        bandwidth, latency, path, server2, server2, burst=2000, video=video
                    )
                    experiments.append(Experiment(
                        video = video,
                        path = str(Path(path) / "leader_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["rmpc", cc1 + '1', cc2 + '2', video],
                        run_id = run_id,
                    ))
        
        # traces
        subpath = str(Path(experiment_path) / "traces")
        server1 = f"--cc target --server-algo target2 --name abrcc --video {video}"
        server2 = f"--cc bbr --algo robustMpc --name robustMpc --video {video}"
        server3 = f"--cc gap --server-algo gap --name abrcc --video {video}"
        server4 = f"--cc gap --server-algo target --name abrcc --video {video}"
        for name, server in [
            ("robustMpc", server2), 
            ("target2", server1),
            ("gap", server3),
            ("gap_pid", server4),
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
                    video = video,
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
def generate_plots(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "plots")
    os.system(f"mkdir -p {experiment_path}")
    
    videos = ['got', 'bojack', 'guard', 'cook']
    for video in videos:
        experiments = sum([load_experiments(experiment) for experiment in [
            str(Path("experiments") / "multiple_videos" / video),
        ]], [])
    
        os.system(f"mkdir -p {experiment_path}/{video}")
        plot_bar(str(Path(experiment_path) / video / "versus_cubic"), experiments, [
            # performance
            (["versus", "cubic", "target", "abbr"], ("abrcc", "target", 1) ),
            (["versus", "cubic", "target2"], ("abrcc", "target2", 1) ),
            (["versus", "cubic", "target", "xbbr"], ("abrcc", "xtarget", 1) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc2", "rmpc_cubic", 1) ),
            #(["rmpc", "bbr1", "bbr2"], (min, "rmpc_bbr", 1) ),
        
            # fairness
            (["versus", "cubic", "target", "abbr"], ("robustMpc", "target", 2) ),
            (["versus", "cubic", "target2"], ("robustMpc", "target2", 2) ),
            (["versus", "cubic", "target", "xbbr"], ("robustMpc", "xtarget", 2) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc1", "rmpc_cubic", 2) ),
            #(["rmpc", "bbr1", "bbr2"], (max, "rmpc_bbr", 2) ),
        ])
        plot_bar(str(Path(experiment_path) / video / "versus_bbr"), experiments, [
            # performance
            (["versus", "bbr", "target", "abbr"], ("abrcc", "target", 1) ),
            (["versus", "bbr", "target2"], ("abrcc", "target2", 1) ),
            (["versus", "bbr", "target", "xbbr"], ("abrcc", "xtarget", 1) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc1", "rmpc_cubic", 1) ),
            #(["rmpc", "cubic1", "bbr2"], ("bbr2", "rmpc_bbr", 1) ),
        
            # fairness
            (["versus", "bbr", "target", "abbr"], ("robustMpc", "target", 2) ),
            (["versus", "bbr", "target2"], ("robustMpc", "target2", 2) ),
            (["versus", "bbr", "target", "xbbr"], ("robustMpc", "xtarget", 2) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc2", "rmpc_cubic", 2) ),
            #(["rmpc", "cubic1", "bbr2"], ("cubic1", "rmpc_bbr", 2) ),
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
