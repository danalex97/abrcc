from typing import Dict, List, Union, Tuple, Callable
from collections import defaultdict

from exp_util.data import Experiment

import math
import datetime
import numpy as np
import matplotlib.pyplot as plt


DPI = 100


Tag = List[str]

Name = str
Instance = Union[str, Callable]
Plane = int

TagMapping = Tuple[Tag, Tuple[Instance, Name, Plane]]


def get_plot_data(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> Dict[Tuple[int, int, str], List[Tuple[Experiment, str]]]:
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
    return plot_data


def get_metrics(
    plot_data: Dict[Tuple[int, int, str], List[Tuple[Experiment, str]]]
) -> Dict[str, List[Tuple[str, float]]]:
    metrics = defaultdict(list)
    for env, exp_inst in plot_data.items():
        latency, bandwidth, trace = env
        
        for exp, instance_name in exp_inst: 
            instance: Instance = instance_name[0]
            name: str = instance_name[1]
            plane: int = instance_name[2]

            if type(instance) == str:
                for metric in exp.get_metrics():
                    if metric.instance == instance:
                        metrics[metric.metric].append((name, metric.value))
            else:
                raise NotImplementedError()
    return metrics


def get_fcts(
    plot_data: Dict[Tuple[int, int, str], List[Tuple[Experiment, str]]]
) -> Dict[str, List[float]]:
    out = defaultdict(list)
    for env, exp_inst in plot_data.items():
        latency, bandwidth, trace = env
        for exp, instance_name in exp_inst:
            instance: Instance = instance_name[0]
            name: str = instance_name[1]
            plane: int = instance_name[2]

            if type(instance) == str:
                fcts = exp.get_flow_completion_times()
                out[name] += [v / 1000. for v in fcts]
            else:
                raise NotImplementedError()
    return out


def plot_fct_cdf(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
    plot_data = get_plot_data(plot_base, experiments, tag_maps)
    fcts      = get_fcts(plot_data)
    
    plot_name = f"{plot_base}.png"
    ax = plt.subplot(111)
    schemes = []
    marker_index = 0
    for scheme, cur_values in fcts.items():
        values, base = np.histogram(cur_values, bins=len(cur_values))
        cumulative   = np.cumsum(values)
        cumulative   = [float(i) / len(values) * 100 for i in cumulative]
        ax.plot(
            base[:-1], 
            cumulative, 
            linewidth=2, 
        )
        schemes.append(scheme)

    ax.get_xaxis().set_visible(True)
    ax.legend(schemes, loc=4)
    plt.ylabel('CDF')
    plt.xlabel('Flow completion time(s)')
    
    plt.savefig(plot_name, dpi=DPI)
    ax.cla()



def plot_cdf(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
    plot_data = get_plot_data(plot_base, experiments, tag_maps)
    metrics   = get_metrics(plot_data)  

    markers = [',', 'o', 'v', '^', '>', '<', 's', 'x', 'D', 'd', '*', '_', '']
    for metric, instance_value in metrics.items():
        if metric == 'raw_qoe':
            continue
        plot_name = f"{plot_base}_{metric}.png"
        
        all_values = defaultdict(list)
        for instance, value in instance_value:
            all_values[instance].append(value)
            all_values[instance] = sorted(all_values[instance])

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
                markersize=5,
            )
            schemes.append(scheme)

        ax.get_xaxis().set_visible(True)
        ax.legend(schemes, loc=2)
        plt.ylabel('CDF')
        plt.xlabel(metric)
        
        plt.savefig(plot_name, dpi=DPI)
        ax.cla()


def plot_bar(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
    plot_data = get_plot_data(plot_base, experiments, tag_maps)
    
    idx = 0
    instances = []
    named_data_matrix = defaultdict(
        lambda: defaultdict(
            lambda: [[] for _ in range(len(plot_data))]
        )
    )
    for env, exp_inst in plot_data.items():
        # get plot path
        latency, bandwidth, trace = env
        
        # get all metrics
        metrics = defaultdict(list)
        for exp, instance_name in exp_inst: 
            instance: Instance = instance_name[0]
            name: str = instance_name[1]
            plane: int = instance_name[2]

            if type(instance) == str:
                for metric in exp.get_metrics():
                    if metric.instance == instance:
                        metrics[(metric.metric, plane)].append((name, metric.value))
            else:
                func = instance
                groups = defaultdict(list)
                for metric in exp.get_metrics():
                    groups[metric.metric].append(metric.value)
                for metric, group in groups.items():
                    metrics[(metric, plane)].append((name, func(group)))

        for metric_name_plane, values in sorted(metrics.items()):
            metric_name, plane = metric_name_plane
            
            # group values for multiple runs
            grouped_values = defaultdict(list)
            for name, value in values:
                grouped_values[name].append(value)
    
            # average multiple runs
            avg_values = []
            for name, vals in grouped_values.items():
                avg = sum(vals) / len(vals)
                std = math.sqrt(sum((val - avg) ** 2 for val in vals))

                avg_values.append((name, avg, std))
        
            named_data_matrix[metric_name][plane][idx] += sorted(avg_values)
            if len(avg_values) > len(instances):
                instances = [n for n, _, _ in sorted(avg_values)]
            
        idx += 1
   
    # complete the data matrix
    pos = {}
    for i, instance in enumerate(instances):
        pos[instance] = i
    
    data_matrix = defaultdict(
        lambda: defaultdict(lambda: [
            [(0, 0)] * len(instances) for _ in range(len(plot_data))
        ])
    )
    for metric, plane_matrix in sorted(named_data_matrix.items()):
        for plane, matrix in sorted(plane_matrix.items()):
            for idx, line in enumerate(matrix):
                for name, value, std in line:
                    data_matrix[metric][plane][idx][pos[name]] = value, std

    # plot stuff
    colors = ['b', 'g', 'r', 'y', 'c', 'm', 'orange', 'mediumspringgreen', 'peru']
    for metric, plane_matrix in data_matrix.items(): 
        if metric == 'raw_qoe':
            continue

        hatches = ['x', None]
        bar_colors = ['lightgray', 'black']
        max_plane = max(plane_matrix.keys())
        if max_plane == 1:
            hatches = [None]
        for plane, matrix in sorted(plane_matrix.items()):
            plot_name = f"{plot_base}_{metric}.png"
           
            data = [[val for val, std in line] for line in matrix]
            std = [[std for val, std in line] for line in matrix]

            ax = plt.subplot(111)
            x = np.arange(len(plot_data))
            
            data_transp = np.transpose(data)
            std_transp = np.transpose(std)

            width = 1. / (len(instances) + 1)
            for i in range(len(data_transp)):
                ax.bar(
                    x + width * i, 
                    data_transp[i], 
                    color = colors[i], 
                    #yerr = std_transp[i],
                    #error_kw=dict(
                    #    ecolor=bar_colors[max_plane - plane], 
                    #    lw=(max_plane - plane + 1) * 2.5, 
                    #    capsize=0, 
                    #    capthick=2,
                    #),
                    width = width * 0.8 ** (max_plane - plane),
                    alpha = 0.7 ** (max_plane - plane + 1),
                    hatch = hatches[plane - 1],
                )
        ax.get_xaxis().set_visible(False)
        plt.ylabel(metric)
       
        ax.legend(instances, loc=1)
        plt.savefig(plot_name, dpi=DPI)
        plt.cla()
