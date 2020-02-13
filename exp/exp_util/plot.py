from typing import List, Union, Tuple, Callable
from collections import defaultdict

from exp_util.data import Experiment

import datetime
import numpy as np
import matplotlib.pyplot as plt


Tags = List[str]
Instance = Union[str, Callable]
Name = str
TagMapping = Tuple[List[str], Tuple[Instance, Name]]


def plot_bar(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
    # [TODO] this assumes single runs for now

    plot_data = defaultdict(list)
    for tags, instance_name in tag_maps:
        for experiment in experiments: 
            if all((tag in experiment.extra) for tag in tags):
                env = (
                    experiment.latency,
                    experiment.bandwidth,
                    experiment.trace,
                )
                plot_data[env].append((experiment, instance_name))

    idx = 0
    instances = []
    data_matrix = defaultdict(lambda: [[] for _ in range(len(plot_data))])
    for env, exp_inst in plot_data.items():
        # get plot path
        latency, bandwidth, trace = env
        
        # get all metrics
        metrics = defaultdict(list)
        for exp, instance_name in exp_inst: 
            instance: Instance = instance_name[0]
            name: str = instance_name[1]

            if type(instance) == str:
                for metric in exp.get_metrics():
                    if metric.instance == instance:
                        metrics[metric.metric].append((name, metric.value))
            else:
                func = instance
                groups = defaultdict(list)
                for metric in exp.get_metrics():
                    groups[metric.metric].append(metric.value)
                for metric, group in groups.items():
                    metrics[metric].append((name, func(group)))

        for metric_name, values in sorted(metrics.items()):
            # group values for multiple runs
            grouped_values = defaultdict(list)
            for name, value in values:
                grouped_values[name].append(value)
           
            # average multiple runs
            avg_values = []
            for name, vals in grouped_values.items():
                avg_values.append((name, sum(vals) / len(vals)))

            data_matrix[metric_name][idx] += [v for _, v in sorted(avg_values)]
            instances = [n for n, _ in sorted(avg_values)]
            
        idx += 1
    

    idx = 0
    colors = ['b', 'g', 'r', 'y', 'c', 'm']
    for metric, matrix in data_matrix.items():
        plot_name = f"{plot_base}_{metric}.png"

        ax = plt.subplot(111)
        x = np.arange(len(plot_data))
        
        transp = np.transpose(matrix)
        width = 1. / (len(instances) + 1)
        for i in range(len(transp)):
            ax.bar(x + width * i, transp[i], color = colors[i], width = width)
        ax.get_xaxis().set_visible(False)
        plt.ylabel(metric)
        
        ax.legend(instances, loc=1)
        plt.savefig(plot_name)
        plt.cla()
        
        idx += 1
