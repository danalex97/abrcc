from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import List, Optional

from abr.video import get_video_chunks
from exp_util.env import experiments, experiment, run_subexp, run_trace, run_traffic
from exp_util.data import Experiment, save_experiments, generate_summary, load_experiments
from exp_util.plot import plot_bar, plot_cdf, plot_fct_cdf

import os
import time
import random


@experiment
def minerva_example(args: Namespace) -> None:
    experiments = []
    root_path = str(Path("test"))
    os.system(f"mkdir -p {root_path}")
   
    latency, bandwidth = 500, 1
    name = 'minerva' 
    algo = 'minerva'
    cc   = 'minerva'
    
    experiment_path = str(Path(root_path)) 
    subpath = str(Path(experiment_path) / "minerva")
    
    server1 = f"--cc {cc} --algo {algo} --server-algo {algo} --name minerva1 --video guard"
    server2 = f"--cc {cc} --algo {algo} --server-algo {algo} --name minerva2 --video bojack"
    
    path = subpath
    run_subexp(bandwidth, latency, path, [server1, server2], burst=2000, video='bojack', force_run=True)


@experiment
def autotarget_training(args: Namespace) -> None:
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


@experiment
def traffic(args: Namespace) -> None:
    global run_traffic
    if args.dry:
        run_traffic = lambda *args, **kwargs: None 

    videos = ['got', 'bojack', 'cook', 'guard']

    root_path = str(Path("experiments") / "traffic")
    os.system(f"mkdir -p {root_path}")
    runner_log = open(str(Path(root_path) / 'exp.log'), 'w')
   
    instances = [
        ('--algo', 'robustMpc', 'cubic'),
        ('--algo', 'robustMpc', 'bbr2'),
        ('--algo', 'dynamic', 'bbr2'),
        ('--algo', 'dynamic', 'cubic'),
        ('--server-algo', 'gap', 'gap'),
    ]

    experiments = []
    experiment_path = str(Path(root_path) / 'fct')
    subpath = experiment_path
    latency = 100
    for bandwidth in [5, 4, 3]:
        for (where, algo, cc) in instances:
            for run_id in range(10):
                video = random.choice(videos)

                server = f"{where} {algo} --name abr --cc {cc} --video {video}" 
                path = str(Path(subpath) / f"{algo}_{cc}_{bandwidth}_run{run_id}")
                
                runner_log.write(f'> {path}\n')
                run_traffic(path, f"{server} -l {latency} -b {bandwidth} --light", headless=args.headless)
               
                cc_name = cc if cc != "gap" else "gap2"
                experiments.append(Experiment(
                    video = video,
                    path = str(Path(path) / "abr_plots.log"),
                    latency = latency,
                    bandwidth = bandwidth,
                    extra = ["fct", algo, cc_name, f"bw{bandwidth}"],
                    run_id = run_id,
                ))
    if args.dry:
        print(experiments)
        print(len(experiments))
    else:
        save_experiments(experiment_path, experiments)
        generate_summary(experiment_path, experiments)
   
    latency = 500
    for video in videos:
        experiments = []
        experiment_path = str(Path(root_path) / video)
        for run_id in range(4):
            for bandwidth in [3, 2, 1]:
                # versus 
                subpath = str(Path(experiment_path) / "versus_rmpc")
                for (where, algo, cc) in instances:
                    server = f"{where} {algo} --name abr --cc {cc} --video {video}" 
                    path = str(Path(subpath) / f"{algo}_{cc}_{bandwidth}_run{run_id}")
                    
                    runner_log.write(f'> {path}\n')
                    run_traffic(path, f"{server} -l {latency} -b {bandwidth}", headless=args.headless)
                    
                    if cc == "gap":
                        cc = "gap2"
                    experiments.append(Experiment(
                        video = video,
                        path = str(Path(path) / "abr_plots.log"),
                        latency = latency,
                        bandwidth = bandwidth,
                        extra = ["traffic", algo, cc, video],
                        run_id = run_id,
                    ))
        
        if args.dry:
            print(experiments)
            print(len(experiments))
        else:
            save_experiments(experiment_path, experiments)
            generate_summary(experiment_path, experiments)


@experiment
def stream_count(args: Namespace) -> None:
    global run_trace, run_subexp
    if args.dry:
        run_trace  = lambda *args, **kwargs: None
        run_subexp = lambda *args, **kwargs: None 

    videos = ['got', 'bojack', 'cook', 'guard']

    root_path = str(Path("experiments") / "stream_count")
    os.system(f"mkdir -p {root_path}")
    runner_log = open(str(Path(root_path) / 'exp.log'), 'w')
   
    algorithms = [
        ('--server-algo', 'gap', 'gap'),
        ('--algo', 'robustMpc', 'cubic'),
        ('--algo', 'robustMpc', 'bbr2'),
        ('--algo', 'dynamic', 'bbr2'),
        ('--algo', 'dynamic', 'cubic'),
    ]

    experiments = []
    experiment_path = str(Path(root_path))
    
    runs      = 5
    latency   = 500
    bandwidth = 4
    min_streams, max_streams = 2, 8

    for stream_number in range(max_streams, min_streams - 1, -1): 
        for run_id in range(runs):
            for (arg, algo, cc) in algorithms:
                run_servers = []
                run_videos  = []
                for i in range(stream_number):
                    video  = random.choice(videos)
                    server = f"{arg} {algo} --name abr{i + 1} --cc {cc} --video {video}"

                    run_videos.append(video)
                    run_servers.append(server)
                
                video_length  = list(zip(map(get_video_chunks, run_videos), run_videos))
                longest_video = max(video_length)[1]

                path = str(Path(experiment_path) / f"{algo}_{cc}_streams{stream_number}_run{run_id}")
                runner_log.write(f'> {path}\n')
                
                run_subexp(
                   bandwidth, latency, path, run_servers, burst=2000, video=longest_video,
                   headless=args.headless, 
                   force_run = True,
                )
                experiments.append(Experiment(
                    video = video,
                    path  = str(Path(path) / "leader_plots.log"),
                    latency = latency,
                    bandwidth = bandwidth, 
                    extra = [f"streams{stream_number}", algo, cc],
                    run_id = run_id,
                ))
        
    if args.dry:
        print(experiments)
        print(len(experiments))
    else:
        save_experiments(experiment_path, experiments)
        generate_summary(experiment_path, experiments)


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
        for run_id in range(4):
            latency = 500
            for bandwidth in [3, 2, 1]:
                # versus 
                subpath = str(Path(experiment_path) / "versus_rmpc")
                for (algo1, cc1) in compete1:
                    for (algo2, cc2) in compete2:
                        server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video}" 
                        server2 = f"--server-algo {algo2} --name abrcc --cc {cc2} --video {video}"
                        
                        path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        if algo1 != 'robustMpc': # since we don't want to repet old experiments
                            path = str(Path(subpath) / f"{algo1}_{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        
                        run_subexp(
                            bandwidth, latency, path, [server1, server2], burst=2000, video=video,
                            headless=args.headless
                        )
                        
                        if cc2 == "gap":
                            cc2 = "gap2"
                        experiments.append(Experiment(
                            video = video,
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = ["versus", algo1, cc1, algo2, cc2, video],
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

                # baselines
                subpath = str(Path(experiment_path) / "rmpc")
                for cc1, cc2 in [('cubic', 'bbr2'), ('bbr2', 'bbr2'), ('cubic', 'cubic')]:
                    for algo in ['robustMpc', 'dynamic']:
                        server1 = f"--algo {algo} --name rmpc1 --cc {cc1} --video {video}"
                        server2 = f"--algo {algo} --name rmpc2 --cc {cc2} --video {video}"

                        path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_run{run_id}")
                        if algo != 'robustMpc': # since we don't want to repet old experiments
                            path = str(Path(subpath) / f"{algo}_{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        run_subexp(
                            bandwidth, latency, path, [server1, server2], burst=2000, video=video,
                            headless=args.headless
                        )

                        extra = 'rmpc'
                        if algo == 'dynamic':
                            extra = 'dynamic'
                        
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
        server6 = f"--cc bbr2 --algo dynamic --name dynamic --video {video}"
        server3 = f"--cc gap --server-algo gap --name abrcc --video {video}"
        server4 = f"--cc gap --server-algo remote --name abrcc --video {video}"
        server5 = f"--cc cubic --algo robustMpc --name robustMpc --video {video}"
        for plot_name, name, server in [
            ("robustMpc", "rmpc_bbr", server2), 
            ("robustMpc", "rmpc_cubic", server5), 
            ("dynamic", "dynamic_bbr", server6), 
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
                run_trace(path, f"{server} -l {latency} -t {trace}", headless=args.headless)
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
        for run_id in range(4):
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
                        if algo1 != 'robustMpc': # since we don't want to repet old experiments
                            path = str(Path(subpath) / f"{algo1}_{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        
                        run_subexp(
                            bandwidth, latency, path, [server1, server3, server2], burst=2000, video=video,
                            headless=args.headless
                        )
                        
                        if cc2 == "gap":
                            cc2 = "gap2"
                        experiments.append(Experiment(
                            video = video,
                            path = str(Path(path) / "leader_plots.log"),
                            latency = latency,
                            bandwidth = bandwidth,
                            extra = ["versus", algo1, cc1, algo2, cc2, video],
                            run_id = run_id,
                        ))

                # same type
                subpath = str(Path(experiment_path) / "rmpc")
                for cc in ['cubic', 'bbr2']:
                    for algo in ['robustMpc', 'dynamic']:
                        server1 = f"--algo {algo} --name rmpc1 --cc {cc} --video {video}"
                        server2 = f"--algo {algo} --name rmpc2 --cc {cc} --video {video}"
                        server3 = f"--algo {algo} --name rmpc3 --cc {cc} --video {video}"

                        path = str(Path(subpath) / f"{cc}_{bandwidth}_run{run_id}")
                        if algo1 != 'robustMpc': # since we don't want to repet old experiments
                            path = str(Path(subpath) / f"{algo1}_{cc}_{bandwidth}_run{run_id}")
                        runner_log.write(f'> {path}\n')
                        run_subexp(
                            bandwidth, latency, path, [server1, server2, server3], burst=2000, video=video,
                            headless=args.headless
                        )

                        extra = 'rmpc'
                        if algo == 'dynamic':
                            extra = 'dynamic'
                       
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
    
    # only for rmpc at the moment
    compete1 = [
        ('robustMpc', 'bbr2'),
        ('dynamic', 'bbr2'),
        # ('robustMpc', 'cubic'), # [TODO]
        # ('dynamic', 'cubic'), # [TODO]
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
                for run_id in range(4):
                    latency = 500
                    # robustMpc vs others 
                    for bandwidth in [3, 2, 1]:
                        subpath = str(Path(experiment_path) / "versus_rmpc")
                        for (algo1, cc1) in compete1:
                            for (algo2, cc2) in compete2:
                                server1 = f"--algo {algo1} --name robustMpc --cc {cc1} --video {video1}" 
                                server2 = f"--server-algo {algo2} --name abrcc --cc {cc2} --video {video2}"
                        
                                path = str(Path(subpath) / f"{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
                                if algo1 != 'robustMpc': # since we don't want to repet old experiments
                                    path = str(Path(subpath) / f"{algo1}_{cc1}_{algo2}_{cc2}_{bandwidth}_run{run_id}")
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
                                    extra = ["versus", algo1, cc1, algo2, cc2, video1, video2],
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
                        for cc1, cc2 in [('cubic', 'bbr2'), ('bbr2', 'bbr2'), ('cubic', 'cubic')]:
                            for algo in ['robustMpc', 'dynamic']:
                                server1 = f"--algo {algo} --name rmpc1 --cc {cc1} --video {video1}"
                                server2 = f"--algo {algo} --name rmpc2 --cc {cc2} --video {video2}"

                                path = str(Path(subpath) / f"{cc1}_{cc2}_{bandwidth}_run{run_id}")
                                if algo1 != 'robustMpc': # since we don't want to repet old experiments
                                    path = str(Path(subpath) / f"{algo}_{cc1}_{cc2}_{bandwidth}_run{run_id}")

                                runner_log.write(f'> {path}\n')
                                run_subexp(
                                    bandwidth, latency, path, [server1, server2], burst=2000, video=longer_video,
                                    headless=args.headless
                                )
                                extra = 'rmpc'
                                if algo == 'dynamic':
                                    extra = 'dynamic'
     
                                experiments.append(Experiment(
                                    video = longer_video,
                                    path = str(Path(path) / "leader_plots.log"),
                                    latency = latency,
                                    bandwidth = bandwidth,
                                    extra = [extra, cc1 + '1', cc2 + '2', video1, video2],
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
    avg = lambda xs: sum(xs) / len(xs)
    cap = lambda xs: max(xs + [-50])

    def plot_multiple(path: str, experiments: List[Experiment], cc: str, func) -> None:
        plot_bar(path, experiments, [
            # fairness
            (["versus", "robustMpc", f"{cc}", "gap2"], (func, "Gap-RobustMpc", 1) ),
            (["versus", "dynamic", f"{cc}", "gap2"], (func, "Gap-Dynamic", 1) ),
            (["rmpc", f"{cc}1", f"{cc}2", f"{cc}3"], (func, "RobustMpc", 1) ),
            (["dynamic", f"{cc}1", f"{cc}2", f"{cc}3"], (func, "Dynamic", 1) ),
        ])

    def plot_multiple2(path: str, experiments: List[Experiment], cc: str) -> None:
        plot_bar(path, experiments, [
            # fairness
            (["versus", "robustMpc", f"{cc}", "gap2"], ('abrcc', "Gap-RobustMpc", 1) ),
            (["versus", "dynamic", f"{cc}", "gap2"], ('abrcc', "Gap-Dynamic", 1) ),
            (["rmpc", f"{cc}1", f"{cc}2", f"{cc}3"], (min, "RobustMpc", 1) ),
            (["dynamic", f"{cc}1", f"{cc}2", f"{cc}3"], (min, "Dynamic", 1) ),
        ])
    
    def plot_versus(path: str, experiments: List[Experiment], cc: str) -> None:
        plot_bar(path, experiments, [
            # performance
            (["versus", "robustMpc", f"{cc}", "gap2"], ("abrcc", "Gap-RobustMpc", 1) ),
            (["versus", "dynamic", f"{cc}", "gap2"], ("abrcc", "Gap-Dynamic", 1) ),
            (["rmpc", f"{cc}1", f"{cc}2"], (max, "RobustMpc", 1) ),
            (["dynamic", f"{cc}1", f"{cc}2"], (max, "Dynamic", 1) ),
        
            # fairness
            (["versus", "robustMpc", f"{cc}", "gap2"], ("robustMpc", "Gap-RobustMpc", 2) ),
            (["versus", "dynamic", f"{cc}", "gap2"], ("robustMpc", "Gap-Dynamic", 2) ),
            (["rmpc", f"{cc}1", f"{cc}2"], (min, "RobustMpc", 2) ),
            (["dynamic", f"{cc}1", f"{cc}2"], (min, "Dynamic", 2) ),
        ])
   
    def plot_self(path: str, experiments: List[Experiment]) -> None:
        plot_bar(path, experiments, [
            (["self", "gap", "gap2"], (min, " Gap", 1) ),
            (["dynamic", "cubic1", "cubic2"], (min, "Dynamic-Cubic", 1) ),
            (["dynamic", "bbr21", "bbr22"], (min, "Dynamic-BBR", 1) ),
            (["rmpc", "cubic1", "cubic2"], (min, "RobustMpc-Cubic", 1) ),
            (["rmpc", "bbr21", "bbr22"], (min, "RobustMpc-BBR", 1) ),
        ])
    
    def plot_self_avg(path: str, experiments: List[Experiment]) -> None:
        plot_bar(path, experiments, [
            (["self", "gap", "gap2"], (avg, " Gap", 1) ),
            (["dynamic", "cubic1", "cubic2"], (avg, "Dynamic-Cubic", 1) ),
            (["dynamic", "bbr21", "bbr22"], (avg, "Dynamic-BBR", 1) ),
            (["rmpc", "cubic1", "cubic2"], (avg, "RobustMpc-Cubic", 1) ),
            (["rmpc", "bbr21", "bbr22"], (avg, "RobustMpc-BBR", 1) ),
        ])
    
    def plot_traces(path: str, experiments: List[Experiment]) -> None:
        plot_cdf(path, experiments, [
            (["traces", "rmpc_bbr"], ("robustMpc", "RobustMpc-BBR", 1) ),
            (["traces", "dynamic_bbr"], ("dynamic", "Dynamic-BBR", 1) ),
            (["traces", "rmpc_cubic"], ("robustMpc", "RobustMpc-Cubic", 1) ),
            (["traces", "gap_pid"], ("abrcc", "Gap", 1) ),
        ])

    def plot_traffic(path: str, experiments: List[Experiment]) -> None:
        plot_bar(path, experiments, [
            (["traffic", "robustMpc", "bbr2"], (cap, "RobustMpc-BBR", 1) ),
            (["traffic", "robustMpc", "cubic"], (cap, "RobustMpc-Cubic", 1) ),
            (["traffic", "dynamic", "bbr2"], (cap, "Dynamic-BBR", 1) ),
            (["traffic", "dynamic", "cubic"], (cap, "Dynamic-Cubic", 1) ),
            (["traffic", "gap"], (cap, "Gap", 1) ),
        ])

    def plot_fct_traffic(path: str, experiments: List[Experiment], bw :Optional[int] = None) -> None:
        extra = [f"bw{bw}"] if bw else []
        plot_fct_cdf(path, experiments, [
            (["fct", "robustMpc", "bbr2"] + extra, ('abr', "RobustMpc-BBR", 1) ),
            (["fct", "robustMpc", "cubic"] + extra, ('abr', "RobustMpc-Cubic", 1) ),
            (["fct", "dynamic", "bbr2"] + extra, ('abr', "Dynamic-BBR", 1) ),
            (["fct", "dynamic", "cubic"] + extra, ('abr', "Dynamic-Cubic", 1) ),
            (["fct", "gap"] + extra, ('abr', "Gap", 1) ),
        ])

    experiment_path = str(Path("experiments") / "plots")
    os.system(f"mkdir -p {experiment_path}")

    # traffic fct
    traffic_path = str(Path(experiment_path) / "traffic")
    os.system(f"mkdir -p {traffic_path}")
    experiments = sum([load_experiments(experiment) for experiment in [
        str(Path("experiments") / "traffic" / "fct"),
    ]], [])
    for bw in [5, 4, 3]:
        plot_fct_traffic(str(Path(traffic_path) / f"fct{bw}"), experiments, bw=bw)
    plot_fct_traffic(str(Path(traffic_path) / "fct"), experiments)
    
    # per-video plots
    videos = ['got', 'bojack', 'guard', 'cook']
    for video in videos:
        experiments = sum([load_experiments(experiment) for experiment in [
            str(Path("experiments") / "multiple_videos" / video),
        ]], [])
    
        os.system(f"mkdir -p {experiment_path}/{video}")
        for cc in ['cubic', 'bbr2']:
            plot_versus(str(Path(experiment_path) / video / f"{cc}"), experiments, cc)
        plot_self(str(Path(experiment_path) / video / "self"), experiments)
        plot_traces(str(Path(experiment_path) / video / "traces"), experiments)

    # 3 flow experiments
    for video in videos:
        experiments = sum([load_experiments(experiment) for experiment in [
            str(Path("experiments") / "multiple_videos2" / video),
        ]], [])
    
        os.system(f"mkdir -p {experiment_path}/{video}")
        for cc in ['cubic', 'bbr2']:
            plot_multiple(str(Path(experiment_path) / video / f"multiple_avg_{cc}"), experiments, cc, avg)
            plot_multiple2(str(Path(experiment_path) / "summary" / f"multiple_fair_{cc}"), experiments, cc)

    # hetero experiments
    videos = ['got', 'bojack', 'guard']
    for i, video1 in enumerate(videos):
        for j, video2 in enumerate(videos):
            if j > i:
                experiments = sum([load_experiments(experiment) for experiment in [
                    str(Path("experiments") / "hetero" / f"{video1}_{video2}"),
                ]], [])
        
                os.system(f"mkdir -p {experiment_path}/{video1}_{video2}")
                for cc in ['cubic', 'bbr2']:
                    plot_versus(str(Path(experiment_path) / f"{video1}_{video2}" / f"{cc}"), experiments, cc)
                plot_self(str(Path(experiment_path) / f"{video1}_{video2}" / "self"), experiments)
                plot_self_avg(str(Path(experiment_path) / f"{video1}_{video2}" / "self_avg"), experiments)

    # traffic
    videos = ['got', 'bojack', 'guard', 'cook']
    for video in videos:
        experiments = sum([load_experiments(experiment) for experiment in [
            str(Path("experiments") / "traffic" / video),
        ]], [])
    
        os.system(f"mkdir -p {experiment_path}/{video}")
        plot_traffic(str(Path(experiment_path) / video / f"traffic"), experiments)
    
    # summaries
    videos = ['got', 'bojack', 'guard', 'cook']
    experiments = sum([load_experiments(experiment) for experiment in [
        str(Path("experiments") / "multiple_videos" / video)
        for video in videos
    ]], [])
    experiments2 = sum([load_experiments(experiment) for experiment in [
        str(Path("experiments") / "multiple_videos" / video)
        for video in ['guard', 'bojack', 'cook']
    ]], [])
    os.system(f"mkdir -p {experiment_path}/summary")
    for cc in ['cubic', 'bbr2']:
        plot_versus(str(Path(experiment_path) / 'summary' / f"{cc}"), experiments, cc)
    plot_self(str(Path(experiment_path) / 'summary' / "self"), experiments)
    plot_traces(str(Path(experiment_path) / 'summary' / "traces"), experiments2)
    
    # summary multiple
    experiments = sum([load_experiments(experiment) for experiment in [
        str(Path("experiments") / "multiple_videos2" / video)
        for video in videos
    ]], [])
    for cc in ['cubic', 'bbr2']:
        plot_multiple(str(Path(experiment_path) / "summary" / f"multiple_avg_{cc}"), experiments, cc, avg)
        plot_multiple2(str(Path(experiment_path) / "summary" / f"multiple_fair_{cc}"), experiments, cc)

    # summary hetero
    experiments = []
    videos = ['got', 'bojack', 'guard']
    for i, video1 in enumerate(videos):
        for j, video2 in enumerate(videos):
            if j > i:
                experiments += sum([load_experiments(experiment) for experiment in [
                    str(Path("experiments") / "hetero" / f"{video1}_{video2}"),
                ]], [])
    for cc in ['cubic', 'bbr2']:
        plot_versus(str(Path(experiment_path) / f"summary" / f"hetero_{cc}"), experiments, cc)
    plot_self(str(Path(experiment_path) / f"summary" / "hetero_self"), experiments)
    plot_self_avg(str(Path(experiment_path) / f"summary" / "hetero_self_avg"), experiments)


@experiment
def run_all(args: Namespace) -> None:
    traffic(args)
    multiple(args)
    multiple2(args)
    hetero(args) 


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
