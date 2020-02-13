from typing import List, Tuple
from collections import defaultdict

from exp_util.data import Experiment

import datetime
import numpy as np
import matplotlib.pyplot as plt


TagMapping = Tuple[List[str], str]


def plot_bar(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
    plot_data = defaultdict(list)
    for tags, instance in tag_maps:
        for experiment in experiments: 
            if all((tag in experiment.extra) for tag in tags):
                env = (
                    experiment.latency,
                    experiment.bandwidth,
                    experiment.trace,
                )
                plot_data[env].append((experiment, instance))

    idx = 0
    instances = []
    data_matrix = defaultdict(lambda: [[] for _ in range(len(plot_data))])
    for env, exp_inst in plot_data.items():
        # get plot path
        latency, bandwidth, trace = env
        plot_name_no_metric = (plot_base + f"_{latency}" 
            + (f"_{bandwidth}" if bandwidth else "_{trace}"))

        # get all metrics
        metrics = defaultdict(list)
        for exp, inst in exp_inst: 
            for metric in exp.get_metrics(): 
                if metric.instance == inst:
                    metrics[metric.metric].append((metric.instance, metric.value))
       
        for metric_name, values in sorted(metrics.items()):
            data_matrix[metric_name][idx] += [v for _, v in sorted(values)]
            instances = [n for n, _ in sorted(values)]
            
        idx += 1
   
    idx = 0
    colors = ['b', 'g', 'r', 'y']
    for metric, matrix in data_matrix.items():
        ax = plt.subplot(111)
        x = np.arange(len(plot_data))
        
        transp = np.transpose(matrix)
        
        for i in range(len(transp)):
            ax.bar(x + .25 * i, transp[i], color = colors[i], width = 0.25)
        ax.get_xaxis().set_visible(False)
        plt.ylabel(metric)
        
        ax.legend(instances, loc=2)
        plt.show()
        plt.cla()
        
        idx += 1
