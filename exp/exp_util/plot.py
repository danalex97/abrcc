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


def plot_cdf(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
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

    # get all metrics
    metrics = defaultdict(list)
    for env, exp_inst in plot_data.items():
        # get plot path
        latency, bandwidth, trace = env
        
        for exp, instance_name in exp_inst: 
            instance: Instance = instance_name[0]
            name: str = instance_name[1]

            if type(instance) == str:
                for metric in exp.get_metrics():
                    if metric.instance == instance:
                        metrics[metric.metric].append((name, metric.value))
            else:
                raise NotImplementedError()

    markers = [',', 'o', 'v', '^', '>', '<', 's', 'x', 'D', 'd', '*', '_', '']
    for metric, instance_value in metrics.items():
        plot_name = f"{plot_base}_{metric}.png"
        
        all_values = defaultdict(list)
        for instance, value in instance_value:
            all_values[instance].append(value)
        
        ax = plt.subplot(111)
        
        schemes = []
        marker_index = 0
        for scheme, cur_values in all_values.items():
            values, base = np.histogram(cur_values, bins=len(cur_values))
            cumulative   = np.cumsum(values)
            cumulative   = [float(i) / len(values) * 100 for i in cumulative]
            
            marker_index = (marker_index + 1) % len(markers)
            ax.plot(
                base[:-1], 
                cumulative, 
                linewidth=2, 
                marker=markers[marker_index], 
                markevery=1, 
                markersize=5,
            )
            schemes.append(scheme)

        ax.legend(schemes, loc=2)
        plt.ylabel('CDF')
        plt.xlabel(metric)
        
        plt.savefig(plot_name)
        ax.cla()


def plot_bar(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
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
    named_data_matrix = defaultdict(lambda: [[] for _ in range(len(plot_data))])
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
            print(grouped_values)
            print()
    
            # average multiple runs
            avg_values = []
            for name, vals in grouped_values.items():
                avg_values.append((name, sum(vals) / len(vals)))

            named_data_matrix[metric_name][idx] += sorted(avg_values)
            if len(avg_values) > len(instances):
                instances = [n for n, _ in sorted(avg_values)]
            
        idx += 1
   
    # complete the data matrix
    pos = {}
    for i, instance in enumerate(instances):
        pos[instance] = i
    
    data_matrix = defaultdict(lambda: [
        [0] * len(instances) for _ in range(len(plot_data))])
    for metric, matrix in named_data_matrix.items():
        for idx, line in enumerate(matrix):
            for name, value in line:
                data_matrix[metric][idx][pos[name]] = value

    # plot stuff
    idx = 0
    colors = ['b', 'g', 'r', 'y', 'c', 'm', 'orange', 'mediumspringgreen', 'peru']
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
