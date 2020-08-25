from typing import Dict, List, Union, Tuple, Callable, Optional
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


def get_flow_capacity(
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
                out[name] += [v * 1000 for v in exp.get_flow_capacity()]
            else:
                raise NotImplementedError()
    return out


def plot_flow_capacity_cdf( 
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
) -> None:
    plot_data  = get_plot_data(plot_base, experiments, tag_maps)
    capacities = get_flow_capacity(plot_data)
    
    plot_name = f"{plot_base}.png"
    ax = plt.subplot(111)
    schemes = []
    marker_index = 0
    for scheme, cur_values in capacities.items():
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
    plt.xlabel('Flow capacity(kbps)')
    
    plt.savefig(plot_name, dpi=DPI)
    ax.cla()


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
    metrics: Optional[List[str]] = None,
    x_labels: Dict[str, str] = {},
) -> None:
    '''
    Generates a CDF plot file at location f'{plot_base}{metric_name}.png'
    from the given {experiments} grouped by {tag_maps}.

    Optinal arguments:
        - metrics: list of metrics to be plotted(all by default)
        - x_labels: mapping for plotted metrics
    '''    
    metrics_to_plot = metrics
    
    plot_data = get_plot_data(plot_base, experiments, tag_maps)
    metrics   = get_metrics(plot_data)  

    markers = [',', 'o', 'v', '^', '>', '<', 's', 'x', 'D', 'd', '*', '_', '']
    for metric, instance_value in metrics.items():
        if metrics is not None:
            if metric not in metrics_to_plot:
                continue
        plot_name = f"{plot_base}_{metric}.png"
        print(f'Summary {plot_name}')

        all_values = defaultdict(list)
        for instance, value in instance_value:
            all_values[instance].append(value)
            all_values[instance] = sorted(all_values[instance])

        ax = plt.subplot(111)
        schemes = []
        marker_index = 0
        for scheme, cur_values in all_values.items():
            avg = sum(cur_values) / len(cur_values)
            median = cur_values[len(cur_values) // 2]
            p5 = cur_values[int(len(cur_values) * .05)]
            p10 = cur_values[int(len(cur_values) * .10)]
            p80 = cur_values[int(len(cur_values) * .80)]
            p95 = cur_values[int(len(cur_values) * .95)]

            print(f'{scheme} avg: {avg}, median: {median}, p5: {p5}, p10: {p10}, p80: {p80}, p95: {p95}') 

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
        plt.xlabel(x_labels.get(metric, metric))
        
        plt.savefig(plot_name, dpi=DPI)
        ax.cla()


def plot_tag(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
    partial_tag: str,
    metrics: Optional[List[str]] = None,
    y_labels: Dict[str, str] = {},
    legend_location: int = 2, 
) -> None: 
    '''
    Generates a line plot file at location f'{plot_base}{metric_name}.png'
    from the given {experiments} grouped by {tag_maps}. The X axis represent the
    different values taken by the {pratial_tag}, while the Y axis represents 
    each indivitual metric.

    Optinal arguments:
        - metrics: list of metrics to be plotted(all by default)
        - y_labels: mapping for plotted metrics
        - legend_location: locationd of the lengend as specified in pyplot.legend
    '''
    metrics_to_plot = metrics

    extra_tags = sorted([el 
        for el in set(sum([e.extra for e in experiments], [])) 
        if partial_tag in el])
   
    plot_data = defaultdict(list)
    for tags, instance_name in tag_maps:
        for tag in extra_tags:
            for experiment in experiments: 
                if all((tag in experiment.extra) for tag in tags + [tag]):
                    plot_data[tag].append((experiment, instance_name))
 
    idx = 0
    instances = []
    named_data_matrix = defaultdict(
        lambda: defaultdict(list)
    )
    for tag, exp_inst in plot_data.items():
        tag_value = int(tag.split(partial_tag)[1])

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
            # planes have no effect
            metric_name, plane = metric_name_plane
            
            # group values for multiple runs
            grouped_values = defaultdict(list)
            for name, value in values:
                grouped_values[name].append(value)
    
            avg_values = []
            for name, vals in grouped_values.items():
                avg = sum(vals) / len(vals)
                avg_values.append((name, avg))
       
            if len(avg_values) > 0:
                named_data_matrix[metric_name][tag_value] += sorted(avg_values)
            if len(avg_values) > len(instances):
                instances = [n for n, _ in sorted(avg_values)]
 
    curves = defaultdict(
        lambda: defaultdict(list)
    )
    for metric, tag_values in named_data_matrix.items():
        for tag_val, values in tag_values.items():
            for algo, value in values:
                curves[metric][algo].append((tag_val, value))

    for metric, metric_curves in curves.items():
        if metrics is not None:
            if metric not in metrics_to_plot:
                continue
        
        plot_name = f"{plot_base}_{metric}.png"
        ax = plt.subplot(111)
        
        schemes = []
        for scheme, curve in metric_curves.items():
            xs = [x for x, _ in curve]
            ys = [y for _, y in curve]
                
            ax.plot(
                xs,
                ys,
                linewidth=2,
            )
            schemes.append(scheme)

        ax.legend(schemes, loc=legend_location)
        plt.ylabel(y_labels.get(metric, metric))
        plt.xlabel(partial_tag)
        
        plt.savefig(plot_name, dpi=DPI)
        ax.cla()


def plot_bar(
    plot_base: str,
    experiments: List[Experiment],
    tag_maps: List[TagMapping],
    x_range: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
    y_labels: Dict[str, str] = {},
    legend_location: int = 1, 
    exclude: List[str] = [],
) -> None:
    '''
    Generates a bar plot file at location f'{plot_base}{metric_name}.png'
    from the given {experiments} grouped by {tag_maps}.

    Optinal arguments:
        - x_range: list of string ticks to add to x axis under the bar plots
        - metrics: list of metrics to be plotted(all by default)
        - y_labels: mapping for plotted metrics
        - legend_location: locationd of the lengend as specified in pyplot.legend
        - exclude: list of algorithms to exclude from plotting
    '''
    plot_data = get_plot_data(plot_base, experiments, tag_maps)
    metrics_to_plot = metrics

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

            if name in exclude:
                continue

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
        if metrics is not None:
            if metric not in metrics_to_plot:
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

            print(f"Summary {plot_name}")
            width = 1. / (len(instances) + 1)
            for i in range(len(data_transp)):
                print(data_transp[i])
                ax.bar(
                    x + width * i, 
                    data_transp[i], 
                    color = colors[i], 
                    width = width * 0.8 ** (max_plane - plane),
                    alpha = 0.7 ** (max_plane - plane + 1),
                    hatch = hatches[plane - 1],
                )
        if x_range is None:
            plt.xticks(
                [i + .5 - 1 / (len(data_transp) + 1) for i in range(len(data_transp[0]))],
                [f'{i+1}Mbps' for i in range(len(data_transp[0]) - 1, -1, -1)], rotation=30
            )
        else:
            plt.xticks(
                [i + .5 - 1 / (len(data_transp) + 1) for i in range(len(data_transp[0]))],
                x_range , rotation = 30
            )
        plt.ylabel(y_labels.get(metric, metric))
       
        ax.legend(instances, loc=legend_location)
        plt.savefig(plot_name, dpi=DPI)
        plt.cla()


