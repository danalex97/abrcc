from typing import List, Optional
from collections import defaultdict
from pathlib import Path

from server.data import JSONType 

import json


class ExperimentMetric:
    def __init__(self, metric: str, instance: str, value: float) -> None:
        self.metric = metric
        self.instance = instance
        self.value = value

    def __str__(self) -> str:
        return f"ExperimentMetric({self.metric} - {self.instance} : {self.value})"
    
    def __repr__(self) -> str:
        return self.__str__()


class RawQoe(ExperimentMetric):
    def __init__(self, instance: str, value: float) -> None:
        super().__init__('raw_qoe', instance, value)


class VmafQoe(ExperimentMetric):
    def __init__(self, instance: str, value: float) -> None:
        super().__init__('vmaf_qoe', instance, value)


class Experiment:
    def __init__(self,
        path: str,
        latency: int, 
        extra: List[str] = [],
        run_id: int = 1,
        bandwidth: Optional[int] = None,
        trace: Optional[str] = None,
    ) -> None:
        self.path = path
        self.bandwidth = bandwidth
        self.trace = trace
        self.extra = extra
        self.latency = latency
        self.run_id = run_id
        self.metrics = []

    def get_metrics(self) -> List[ExperimentMetric]:
        try:
            with open(self.path, 'r') as graph_log:
                raw_qoe = defaultdict(lambda: defaultdict(int))
                vmaf_qoe = defaultdict(lambda: defaultdict(int))
                
                for line in graph_log.read().split('\n'):
                    def proc_metric(curr_dict, metric):
                        if metric not in obj:
                            return
                        x = obj['x']
                        for name, value in obj[metric].items():
                            # not great
                            if x != 0 and x != 49:
                                curr_dict[name][x] = value
                    
                    try:
                        obj = json.loads(line)
                    except:
                        pass
                    proc_metric(raw_qoe, "raw_qoe")
                    proc_metric(vmaf_qoe, "vmaf_qoe")

                out = []
                for name in raw_qoe.keys():
                    qoe_vals = list(raw_qoe[name].values())
                    total_qoe = sum(qoe_vals) / len(qoe_vals)

                    vmaf_vals = list(vmaf_qoe[name].values())
                    total_vmaf = sum(vmaf_vals)
                    
                    out.append(RawQoe(name, total_qoe))
                    out.append(VmafQoe(name, total_vmaf))
                return out
        except FileNotFoundError as e:
            return []

    @staticmethod
    def from_json(json: JSONType) -> 'Experiment':
        return Experiment(
            path = json['path'],
            latency = json['latency'],
            extra = json['extra'],
            run_id = json['run_id'],
            bandwidth = json.get('bandwidth', None),
            trace = json.get('trace', None),
        )

    @property
    def json(self) -> JSONType:
        out = {
            'path' : self.path,
            'latency' : self.latency,
            'extra' : self.extra,
            'run_id' : self.run_id,
        }
        if self.bandwidth:
            out['bandwidth'] = self.bandwidth
        if self.trace:
            out['trace'] = self.trace
        return out
    
    def __str__(self) -> str:
        return f"Experiment({self.json})"
    
    def __repr__(self) -> str:
        return self.__str__()


def save_experiments(path: str, experiments: List[Experiment]) -> None:
    with open(str(Path(path) / 'experiments.txt'), "w") as log:
        for experiment in experiments:
            log.write(json.dumps(experiment.json))
            log.write('\n')

def load_experiments(path: str) -> List[Experiment]:
    try:
        with open(str(Path(path) / 'experiments.txt'), "r") as log:
            contents = log.read()
            return [Experiment.from_json(json.loads(line)) 
                for line in contents.split('\n') if line != ""]
    except FileNotFoundError as e:
        return []


def generate_summary(path: str, experiments: List[Experiment]) -> None:
    with open(str(Path(path) / "log.txt"), "w") as summary:
        for experiment in experiments:  
            summary.write(f'> [{experiment.path}]')
            for metric in experiment.get_metrics():
                summary.write(f' {metric.metric}: {metric.value};')
            summary.write('\n') 