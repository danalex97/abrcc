import asyncio
import multiprocessing
import shutil
import threading
import os
import json
import requests
from os import listdir
from os.path import isfile, join
from server.server import post_after_async
from server.server import component

from argparse import ArgumentParser, Namespace
from pathlib import Path

from server.process import kill_subprocess
from components.monitor import Monitor 
from components.plots import attach_plot_components
from components.complete import OnComplete
from controller import Controller
from server.server import Server, JSONType, multiple_sync
from scripts.network import Network
from typing import List, Dict


def get_replay_log(algo: str, log_path: str) -> List[JSONType]:
    with open(log_path, 'r') as f:
        return list(map(json.loads, f.read().split('\n')[:-1]))
    

async def replay_async(algo: str, log: List[JSONType], monitor: Monitor) -> None:
    await asyncio.sleep(2)
    for entry in log:
        await monitor.process({'stats' : entry})
        if "robust" in algo or "rmpc" in algo:
            await asyncio.sleep(.1)
        else:
            await asyncio.sleep(.01)


async def complete_after(futures: List[asyncio.Future], port: int) -> None:
    await asyncio.gather(*futures)
    await asyncio.sleep(5)
    post_after_async({}, 0, '/complete', port)


@component
async def on_complete(_req: JSONType) -> JSONType:
    kill_subprocess(os.getpid())
    return 'OK'


def run(args: Namespace) -> None:
    # give arguments
    directory = Path(args.dir)
    video = args.video
    name = args.name

    print(f'Replaying {directory} @ {video}')

    # default arguments
    port = 5000

    # find the logs
    files = [
        f for f in listdir(str(directory)) 
        if isfile(str(directory / f)) and "metrics" in f
    ]
    algo_to_log_dir = {
        f.split('_')[0] : str(directory / f)
        for f in files
    }
    algo_to_log = {}
    for algo, log_path in algo_to_log_dir.items():
        log = get_replay_log(algo, log_path)
        algo_to_log[algo] = log

    monitors = {}
    server = Server('experiment', port)
    for algo in algo_to_log.keys():
        # add post for each metrics
        monitors[algo] = Monitor(
            video = args.video,
            path = directory, 
            name = algo,
            plot = True, 
            request_port = port,
            port = port,
            training = False,
            log_to_file = False,
        )
    
    # attach plotter
    plots = attach_plot_components(
        video,
        server,
        trace = getattr(args, 'trace', None),
        no_plot = False,
    )
    server.add_post('/complete', 
        multiple_sync(
            OnComplete(directory, name, plots, video),
            on_complete 
        )
    )
   
    futures = []
    for algo, log in algo_to_log.items():
        futures.append(replay_async(algo, log, monitors[algo]))
   
    # start server
    # multiprocessing.Process(target=server.run).start()

    # run monitors
    def start():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.ensure_future(complete_after(futures, port))
        loop.run_forever()
    multiprocessing.Process(target=start).start()
    server.run()

if __name__ == "__main__":
    parser = ArgumentParser(description='Recompute metrics from a single video instance.')
    parser.add_argument('dir', type=str, help='Location of log folder.')
    parser.add_argument('video', type=str, help='Video to be replayed.')
    parser.add_argument('name', type=str, help='Name of generated plot log.')
    parser.add_argument('-t', '--trace', type=str, help='Trace of bandwidth.')
    run(parser.parse_args())   
