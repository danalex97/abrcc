from argparse import ArgumentParser, Namespace
from pathlib import Path

from abr.video import get_video_chunks
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
    videos = ['guard']

    experiments = []
    root_path = str(Path("test"))
    os.system(f"mkdir -p {root_path}")
   
    compete1 = [
        ('robustMpc', 'bbr'),
    ]
    compete2 = [
        ('gap', 'gap')
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
                        #server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video}" 
                        server1 = f"--server-algo {algo2} --name abrcc1 --cc {cc2} --video {video}"
                        server2 = f"--server-algo {algo2} --name abrcc2 --cc {cc2} --video {video}"
                        
                        path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        run_subexp(bandwidth, latency, path, [server1, server2], burst=2000, video=video, force_run=True)


@experiment
def test2(args: Namespace) -> None:
    videos = ['guard']

    experiments = []
    root_path = str(Path("test"))
    os.system(f"mkdir -p {root_path}")
   
    algos = [
        ('gap', 'gap', 'gap')
    ]
    latency = 500

    for (name, algo, cc) in algos:
        for video in videos:
            experiment_path = str(Path(root_path) / video) 
            subpath = str(Path(experiment_path) / "traces")
            
            traces = Path("network_traces")

            server = f"--cc {cc} --server-algo {algo} --name abrcc --video {video}"
            for trace in [
                str(traces / "norway_tram_5.txt"), 
            ]:
                trace_name = trace.split('/')[-1].split('.')[0]
                path = str(Path(subpath) / f'{name}_{trace_name}')
                run_trace(path, f"{server} -l {latency} -t {trace}", force_run=True)


@experiment
def test3(args: Namespace) -> None:
    videos = ['bojack', 'guard']

    experiments = []
    root_path = str(Path("test"))
    os.system(f"mkdir -p {root_path}")
   
    compete1 = [
        ('dynamic', 'bbr2'),
    ]
    compete2 = [
        ('remote', 'target')
    ]

    for run_id in range(100):
        for video in videos:
            experiment_path = str(Path(root_path) / video)
            latency = 500
            for bandwidth in [1, 2, 3]:
                subpath = str(Path(experiment_path) / "versus_rmpc")
                for (algo1, cc1) in compete1:
                    for (algo2, cc2) in compete2:
                        server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video} --training" 
                        server2 = f"--server-algo {algo2} --name abrcc --cc {cc2} --video {video} --training"
                        
                        path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        run_subexp(
                            bandwidth, latency, path, [server1, server2], burst=2000, video=video, force_run=True,
                        )


def check_replays(video, bandwidth, path):
    return
    if video == "got" and bandwidth == 1:
        os.system(f'python3 replay.py {path} got')
    if video == "guard":
        os.system(f'python3 replay.py {path} guard')
    if video == "cook" and bandwidth < 3:
        os.system(f'python3 replay.py {path} cook')
    if video == "bojack" and bandwidth == 1:
        os.system(f'python3 replay.py {path} bojack')


@experiment
def multiple(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    videos = ['got', 'bojack', 'cook', 'guard']

    root_path = str(Path("experiments") / "multiple_videos")
    os.system(f"mkdir -p {root_path}")
    runner_log = open(str(Path(root_path) / 'exp.log'), 'w')
   
    compete1 = [
        ('robustMpc', 'cubic'),
        ('robustMpc', 'bbr'),
        ('robustMpc', 'bbr2'),
        ('dynamic', 'bbr2'),
        ('dynamic', 'cubic'),
    ]
    compete2 = [
        ('gap', 'gap'),
        # ('remote', 'target')
    ]

    for video in videos:
        experiments = []
        experiment_path = str(Path(root_path) / video)
        for run_id in range(3):
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
                        
                        run_subexp(
                            bandwidth, latency, path, [server1, server2], burst=2000, video=video,
                            headless=args.headless
                        )
                        
                        check_replays(video, bandwidth, path)
                        if cc2 == "gap":
                            cc2 = "gap2"
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
                    run_subexp(
                        bandwidth, latency, path, [server1, server2], burst=2000, video=video,
                        headless=args.headless
                    )
                    
                    if cc == "gap":
                        cc = "gap2"
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
                for cc1, cc2 in [('cubic', 'bbr2'), ('bbr2', 'bbr2'), ('cubic', 'cubic')]:
                    for algo in ['robustMpc', 'dynamic']:
                        server1 = f"--algo {algo} --name rmpc1 --cc {cc1} --video {video}"
                        server2 = f"--algo {algo} --name rmpc2 --cc {cc2} --video {video}"

                        path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        run_subexp(
                            bandwidth, latency, path, [server1, server2], burst=2000, video=video,
                            headless=args.headless
                        )

                        extra = 'rmpc'
                        if algo == 'dynamic':
                            extra = 'dynamic'
                        
                        # check_replays(video, bandwidth, path)
                        experiments.append(Experiment(
                            video = video,
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = [extra, cc1 + '1', cc2 + '2', video],
                            run_id = run_id,
                        ))
        
        # traces
        subpath = str(Path(experiment_path) / "traces")
        server1 = f"--cc target --server-algo target2 --name abrcc --video {video}"
        server2 = f"--cc bbr2 --algo robustMpc --name robustMpc --video {video}"
        server3 = f"--cc gap --server-algo gap --name abrcc --video {video}"
        server4 = f"--cc gap --server-algo remote --name abrcc --video {video}"
        server5 = f"--cc cubic --algo robustMpc --name robustMpc --video {video}"
        for plot_name, name, server in [
            ("robustMpc", "rmpc_bbr", server2), 
            ("robustMpc", "rmpc_cubic", server5), 
            ("abrcc", "target2", server1),
            ("abrcc", "gap_pid", server3), 
            ("abrcc", "remote", server4),
        ]:
            traces = Path("network_traces")
            for trace in [
                str(traces / "norway_train_13.txt"),
                
                str(traces / "car.txt"), 
                str(traces / "bus.txt"), 
                str(traces / "bus1.txt"), 
                
                str(traces / "norway_train_6.txt"),

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
                    path = str(Path(path) / f"{plot_name}_plots.log"),
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
def multiple2(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    videos = ['got', 'bojack', 'cook', 'guard']

    root_path = str(Path("experiments") / "multiple_videos2")
    os.system(f"mkdir -p {root_path}")
    runner_log = open(str(Path(root_path) / 'exp.log'), 'w')
   
    compete1 = [
        ('robustMpc', 'cubic'),
        ('robustMpc', 'bbr2'),
        ('dynamic', 'bbr2'),
        ('dynamic', 'cubic'),
    ]
    compete2 = [
        ('gap', 'gap'),
    ]

    for video in videos:
        experiments = []
        experiment_path = str(Path(root_path) / video)
        for run_id in range(3):
            latency = 500
            for bandwidth in [4, 3, 2]:
                # versus 
                subpath = str(Path(experiment_path) / "versus")
                for (algo1, cc1) in compete1:
                    for (algo2, cc2) in compete2:
                        server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video}" 
                        server3 = f"--algo {algo1} --name robustMpc2 --cc {cc1} --video {video}" 
                        server2 = f"--server-algo {algo2} --name abrcc --cc {cc2} --video {video}"
                        
                        path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        
                        run_subexp(
                            bandwidth, latency, path, [server1, server3, server2], burst=2000, video=video,
                            headless=args.headless
                        )
                        
                        check_replays(video, bandwidth, path)
                        if cc2 == "gap":
                            cc2 = "gap2"
                        experiments.append(Experiment(
                            video = video,
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = ["versus", cc1, algo2, cc2, video],
                            run_id = run_id,
                        ))

                # same type
                subpath = str(Path(experiment_path) / "rmpc")
                for cc in ['cubic', 'bbr']:
                    for algo in ['robustMpc']:
                        server1 = f"--algo {algo} --name rmpc1 --cc {cc} --video {video}"
                        server2 = f"--algo {algo} --name rmpc2 --cc {cc} --video {video}"
                        server3 = f"--algo {algo} --name rmpc3 --cc {cc} --video {video}"

                        path = str(Path(subpath) / f"{cc}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        run_subexp(
                            bandwidth, latency, path, [server1, server2, server3], burst=2000, video=video,
                            headless=args.headless
                        )

                        extra = 'rmpc'
                        if algo == 'dynamic':
                            extra = 'dynamic'
                        
                        # check_replays(video, bandwidth, path)
                        experiments.append(Experiment(
                            video = video,
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = [extra, cc + '1', cc + '2', cc + '3', video],
                            run_id = run_id,
                        ))
        
        if args.dry:
            print(experiments)
            print(len(experiments))
        else:
            save_experiments(experiment_path, experiments)
            generate_summary(experiment_path, experiments)


@experiment
def hetero(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    videos = ['got', 'bojack', 'guard']

    root_path = str(Path("experiments") / "hetero")
    os.system(f"mkdir -p {root_path}")
    runner_log = open(str(Path(root_path) / 'exp.log'), 'w')
   
    compete1 = [
        ('robustMpc', 'bbr2'),
    ]
    compete2 = [
        ('gap', 'gap'),
    ]

    for i, video1 in enumerate(videos):
        for j, video2 in enumerate(videos):
            if j > i:
                longer_video = video1 if get_video_chunks(video1) > get_video_chunks(video2) else video2
                experiments = []
                experiment_path = str(Path(root_path) / f"{video1}_{video2}")
                for run_id in range(3):
                    latency = 500
                    # robustMpc vs others 
                    for bandwidth in [3, 2, 1]:
                        subpath = str(Path(experiment_path) / "versus_rmpc")
                        for (algo1, cc1) in compete1:
                            for (algo2, cc2) in compete2:
                                server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video1}" 
                                server2 = f"--server-algo {algo2} --name abrcc --cc {cc2} --video {video2}"
                        
                                path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                                runner_log.write(f'> {path}\n')
                       
                                run_subexp(
                                    bandwidth, latency, path, [server1, server2], burst=2000, video=longer_video,
                                    headless=args.headless
                                )
                                if cc2 == "gap":
                                    cc2 = "gap2"
                                experiments.append(Experiment(
                                    video = longer_video,
                                    path = str(Path(path) / "leader_plots.log"),
                                    latency = latency,
                                    bandwidth = bandwidth,
                                    extra = ["versus", cc1, algo2, cc2, video1, video2],
                                    run_id = run_id,
                                ))

                        # self
                        subpath = str(Path(experiment_path) / "versus_self")
                        for (algo, cc) in compete2:
                            server1 = f"--server-algo {algo} --name abrcc1 --cc {cc} --video {video1}"
                            server2 = f"--server-algo {algo} --name abrcc2 --cc {cc} --video {video2}"
                        
                            path = str(Path(subpath) / f"{algo}_{cc}_{bandwidth}_run{run_id}")
                            runner_log.write(f'> {path}\n')
                            run_subexp(
                                bandwidth, latency, path, [server1, server2], burst=2000, video=longer_video, 
                                headless=args.headless
                            )
                        
                            if cc == "gap":
                                cc = "gap2"
                            experiments.append(Experiment(
                                video = longer_video,
                                path = str(Path(path) / "leader_plots.log"),
                                latency = latency,
                                bandwidth = bandwidth,
                                extra = ["self", algo, cc, video1, video2],
                                run_id = run_id,
                            ))

                        # robustMpc
                        subpath = str(Path(experiment_path) / "rmpc")
                        for cc1, cc2 in [('cubic', 'bbr'), ('bbr', 'bbr')]:
                            server1 = f"--algo robustMpc --name rmpc1 --cc {cc1} --video {video1}"
                            server2 = f"--algo robustMpc --name rmpc2 --cc {cc2} --video {video2}"

                            path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_run{run_id}")
                            runner_log.write(f'> {path}\n')
                            run_subexp(
                                bandwidth, latency, path, [server1, server2], burst=2000, video=longer_video,
                                headless=args.headless
                            )
                            # check_replays(video, bandwidth, path)
                            experiments.append(Experiment(
                                video = longer_video,
                                path = str(Path(path) / "leader_plots.log"),
                                latency = latency,
                                bandwidth = bandwidth,
                                extra = ["rmpc", cc1 + '1', cc2 + '2', video1, video2],
                                run_id = run_id,
                            ))
                if args.dry:
                    print(experiments)
                    print(len(experiments))
                else:
                    save_experiments(experiment_path, experiments)
                    generate_summary(experiment_path, experiments)


@experiment
def generate_plots_hetero(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "plots")
    os.system(f"mkdir -p {experiment_path}")
    
    videos = ['got', 'bojack', 'guard']
    for i, video1 in enumerate(videos):
        for j, video2 in enumerate(videos):
            if j > i:
                longer_video = video1 if get_video_chunks(video1) > get_video_chunks(video2) else video2
                experiments = sum([load_experiments(experiment) for experiment in [
                    str(Path("experiments") / "hetero" / f"{video1}_{video2}"),
                ]], [])
        
                os.system(f"mkdir -p {experiment_path}/{video1}_{video2}")
                plot_bar(str(Path(experiment_path) / f"{video1}_{video2}" / "versus_bbr"), experiments, [
                    # performance
                    (["versus", "bbr", "gap2"], ("abrcc", "gap-pid", 1) ),
                    (["versus", "bbr", "gap"], ("abrcc", "gap", 1) ),
                    (["rmpc", "cubic1", "bbr2"], ("rmpc2", "rmpc_cubic", 1) ),
                
                    # fairness
                    (["versus", "bbr", "gap2"], ("robustMpc", "gap-pid", 2) ),
                    (["versus", "bbr", "gap"], ("robustMpc", "gap", 2) ),
                    (["rmpc", "cubic1", "bbr2"], ("rmpc1", "rmpc_cubic", 2) ),
                ])
                plot_bar(str(Path(experiment_path) / f"{video1}_{video2}" / "self"), experiments, [
                    # performance
                    (["self", "gap", "gap2"], (sum, "gap-pid", 1) ),
                    (["self", "gap", "target"], (sum, "gap", 1) ),
                    (["rmpc", "bbr1", "bbr2"], (sum, "rmpc_bbr", 1) ),
                ])



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
            (["versus", "cubic", "remote"], ("abrcc", "auto-target", 1) ),
            (["versus", "cubic", "gap2"], ("abrcc", "gap-pid", 1) ),
            (["versus", "cubic", "gap"], ("abrcc", "gap", 1) ),
            #(["versus", "cubic", "target2"], ("abrcc", "target2", 1) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc2", "rmpc-cubic", 1) ),
        
            # fairness
            (["versus", "cubic", "remote"], ("robustMpc", "auto-target", 2) ),
            (["versus", "cubic", "gap2"], ("robustMpc", "gap-pid", 2) ),
            (["versus", "cubic", "gap"], ("robustMpc", "gap", 2) ),
            #(["versus", "cubic", "target2"], ("robustMpc", "target2", 2) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc1", "rmpc-cubic", 2) ),
        ])
        plot_bar(str(Path(experiment_path) / video / "versus_bbr"), experiments, [
            # performance
            (["versus", "bbr", "remote"], ("abrcc", "auto-target", 1) ),
            (["versus", "bbr", "gap2"], ("abrcc", "gap-pid", 1) ),
            (["versus", "bbr", "gap"], ("abrcc", "gap", 1) ),
            #(["versus", "bbr", "target2"], ("abrcc", "target2", 1) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc1", "rmpc_cubic", 1) ),
        
            # fairness
            (["versus", "bbr", "remote"], ("robustMpc", "auto-target", 2) ),
            (["versus", "bbr", "gap2"], ("robustMpc", "gap-pid", 2) ),
            (["versus", "bbr", "gap"], ("robustMpc", "gap", 2) ),
            #(["versus", "bbr", "target2"], ("robustMpc", "target2", 2) ),
            (["rmpc", "cubic1", "bbr2"], ("rmpc2", "rmpc_cubic", 2) ),
        ])
        plot_bar(str(Path(experiment_path) / video / "self"), experiments, [
            # performance
            (["self", "remote"], (min, "auto-target", 1) ),
            (["self", "gap", "gap2"], (min, "gap-pid", 1) ),
            (["self", "gap", "target"], (min, "gap", 1) ),
            #(["self", "target2", "target"], (min, "target2", 1) ),
            (["rmpc", "bbr1", "bbr2"], (min, "rmpc_bbr", 1) ),
            (["rmpc", "cubic1", "cubic2"], (min, "rmpc_bbr", 1) ),
        ])


@experiment
def run_all(args: Namespace) -> None:
    multiple(args)
    multiple2(args)
    hetero(args) 


@experiment
def plot_traces(args: Namespace) -> None:
    experiment_path = str(Path("experiments") / "plots")
    os.system(f"mkdir -p {experiment_path}")
    
    videos = ['got', 'bojack', 'guard', 'cook']
    for video in videos:
        experiments = sum([load_experiments(experiment) for experiment in [
            str(Path("experiments") / "multiple_videos" / video),
        ]], [])
    
        os.system(f"mkdir -p {experiment_path}/{video}")
        plot_cdf(str(Path(experiment_path) / video / "traces"), experiments, [
            (["traces", "robustMpc"], ("robustMpc", "robustMpc", 1) ),
            (["traces", "target2"], ("abrcc", "target2", 1) ),
            (["traces", "gap_pid"], ("abrcc", "gap-pid", 1) ),
            (["traces", "remote"], ("abrcc", "auto-target", 1) ),
        ])


if __name__ == "__main__":
    parser = ArgumentParser(description=
        f'Run experiment setup in this Python file. ' +
        f'Available experiments: {list(experiments().keys())}')
    parser.add_argument('name', type=str, help='Experiment name.')
    parser.add_argument('-d', '--dry', action='store_true', dest='dry', help='Dry run.')
    parser.add_argument('-hl', '--headless', action='store_true', dest='headless', help='Hide the UI.')
    args = parser.parse_args()

    if args.name in experiments():
        experiments()[args.name](args)
    else:
        print(f'No such experiment: {args.name}')
        print(f'Available experiments: {list(EXPERIMENTS.keys())}')
