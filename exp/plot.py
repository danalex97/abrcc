import argparse
import json
import matplotlib.pyplot as plt
import numpy as np 
import os
import pandas as pd
import seaborn as sns 

from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Optional

from components.monitor import MetricsProcessor
from server.data import Metrics 


NUM_BINS = 100
PENSIEVE_VIDEO_CSV = None


def get_vmaf(index: int, bitrate: int) -> float:
    global PENSIEVE_VIDEO_CSV
    if PENSIEVE_VIDEO_CSV is None:
        directory = Path(os.path.dirname(os.path.realpath(__file__)))
        pensieve_path = str(directory / 'video_info' / 'video_info.csv')
        PENSIEVE_VIDEO_CSV = pd.read_csv(pensieve_path)
    video_mappings = {
        '300': '320x180x30_vmaf_score',
        '750': '640x360x30_vmaf_score',
        '1200': '768x432x30_vmaf_score',    
        '1850': '1024x576x30_vmaf_score',  
        '2850': '1280x720x30_vmaf_score',
        '4300': '1280x720x60_vmaf_score',
    }
    str_bitrate = str(int(bitrate))
    return float(PENSIEVE_VIDEO_CSV.loc[index - 1, video_mappings[str_bitrate]])


def get_qoe(
    abr: str, 
    trace: str,
) -> Dict[str, float]: 
    rebuf_penalty = 25
    switching_penalty = 2.5
    segment_length = 4.0

    reward_vmaf = 0.0
    reward_bitrate = 0.0
    total_rebuffering = 0.0
    vmaf_avg = 0.0
    vmaf_switching_avg = 0.0
    bitrate_avg = 0.0
    bitrate_switching_avg = 0.0
    chunks = 0
    first = True

    with open(trace) as f:
        processor = MetricsProcessor()
        lines   = f.read().split('\n')
        metrics = [Metrics.from_json(json.loads(l)) for l in lines if l != ""] 
        
        for metric in metrics:
            for processed_metrics in processor.compute_qoe(metric): 
                chunks += 1
                
                rebuffer = processed_metrics['rebuffer']
                switch = processed_metrics['switch']
                quality = processed_metrics['quality']
                reward = processed_metrics['qoe']
                
                index = processed_metrics['index']
                if first:
                    bitrate = int(quality)
                    bitrate_previous = bitrate
                    vmaf_previous    = get_vmaf(index, bitrate)
                    first = False
                else:
                    bitrate = int(quality)
                    bitrate_avg += bitrate
                    bitrate_switching_avg += abs(bitrate - bitrate_previous)
                    
                    reward_bitrate += float(reward)
                    total_rebuffering += float(rebuffer)
                    
                    vmaf_current = get_vmaf(index, bitrate)
                    vmaf_avg += vmaf_current
                    vmaf_switching_avg += abs(vmaf_current - vmaf_previous)

                    reward_vmaf += (vmaf_current - 
                                    rebuf_penalty * rebuffer / 1000. - 
                                    switching_penalty * abs(vmaf_current - vmaf_previous))
                    
                    vmaf_previous = vmaf_current
                    bitrate_previous = bitrate
    return {
        'reward_vmaf' : reward_vmaf,
        'reward_br' : reward_bitrate,
        'rebuf' : total_rebuffering,
        'switching_br' : bitrate_switching_avg / (segment_length * chunks),
        'switching_vmaf' : vmaf_switching_avg / (segment_length * chunks),
        'vmaf_avg' : vmaf_avg / (segment_length * chunks),
        'br_avg' : bitrate_avg / chunks,
    }


def get_abrs(experiment: str) -> List[str]:
    return list({
        (name.split('_')[0] if '_' in name else None)
        for name in os.listdir(experiment)
    } - {'leader', None})


def get_qoes(
    experiment: str,
) -> Dict[str, Dict[str, List[float]]]:
    results = defaultdict(lambda: defaultdict(list))
    for trace_dir in os.listdir(experiment):
        if os.path.isdir(str(Path(experiment) / trace_dir)):
            abrs = get_abrs(str(Path(experiment) / trace_dir))
            for abr in abrs:
                trace = Path(experiment) / trace_dir / f"{abr}_metrics.log"
                if not os.path.isfile(trace):
                    trace = Path(experiment) / trace_dir / "metrics.log"
                qoe_metrics = get_qoe(abr, trace)
                if qoe_metrics['reward_vmaf'] is not None:
                    for metric, value in qoe_metrics.items():
                        results[abr][metric].append(value)
    return results


def plot_cdf(
    results: Dict[str, Dict[str, List[float]]], 
    reward_key: str,
    store_dir: str,
) -> None:
    fig = plt.figure(figsize=(16.0, 10.0))
    ax = fig.add_subplot(111)
    
    def average_of_the_best() -> float:
        avg_best = -1000000000000
        abr_best = ''
        for scheme in results.keys():
            avg_tmp = np.mean(results[scheme][reward_key])
            if avg_best < avg_tmp:
                avg_best = avg_tmp
                abr_best = scheme
        print("Best provider in average is {} with {}".format(abr_best, avg_best))
        return abs(avg_best)

    schemes = []
    norm = average_of_the_best()
    markers = ['.', ',', 'o', 'v', '^', '>', '<', 's', 'x', 'D', 'd', '*', '_', '']

    for i, scheme in enumerate(results.keys()):
        values       = [float(i) / norm for i in results[scheme][reward_key]]
        values, base = np.histogram(values, bins=len(values))
        cumulative   = np.cumsum(values)
        cumulative   = [float(i) / len(values) * 100 for i in cumulative]
        marker_index = i % len(markers)
        ax.plot(base[:-1], cumulative, linewidth=3, marker=markers[marker_index], markevery=2, markersize=15)
        schemes.append(scheme)

    ax.legend(schemes, loc=2)
    ax.set_xlim(-1, 3)
    plt.ylabel('CDF')
    plt.xlabel('total reward')
    fig.savefig(os.path.join(store_dir, 'cdf_{}.png'.format(reward_key)))


def plot_bar(
    results: Dict[str, Dict[str, List[float]]], 
    metric: str,
    store_dir: str,
) -> None:
    results_metric_avg = {}
    for scheme in results.keys():
        results_metric_avg[scheme] = np.mean(results[scheme][metric])
    fig = plt.figure(figsize=(16.0, 10.0))
    ax = fig.add_subplot(111)
 
    y_pos = np.arange(len(results_metric_avg.keys()))
    ax.bar(y_pos, results_metric_avg.values())
    ax.set_xticks(y_pos)
    ax.set_xticklabels(results_metric_avg.keys())

    fig.savefig(os.path.join(store_dir, 'bar_{}.png'.format(metric)))


def plot_experiment(experiment: str, store_dir: Optional[str] = None) -> None:
    sns.set()
    sns.set_context("talk")

    metric_list = [
        "reward_vmaf", "reward_br", "rebuf", "br_avg", 
        "vmaf_avg", "switching_vmaf", "switching_br",
    ]
    if store_dir is None:
        store_dir = experiment
    res = get_qoes(args.experiment)
    for metric in metric_list:
        if "reward" in metric:
            plot_cdf(res, metric, store_dir)
        plot_bar(res, metric, store_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment",  help='Experiment name.')
    parser.add_argument('--store-dir', dest='store_dir', help='Place to save the plots.', type=str)
    args = parser.parse_args()
   
    store_dir = args.store_dir
    if store_dir and not os.path.exists(store_dir):
        os.makedirs(store_dir)

    plot_experiment(args.experiment, store_dir)
