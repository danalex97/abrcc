from typing import List, Optional
from collections import defaultdict
from pathlib import Path

from server.data import JSONType 
from abr.video import get_approx_video_length, get_video_chunks

import json


class ExperimentMetric:
    """
    Per-experiment or time-bound data point metric. 
      - metric: metadata name of the metric
      - instance: experiment instance path
      - value: the float data point metric
    """
    def __init__(self, metric: str, instance: str, value: float) -> None:
        self.metric = metric
        self.instance = instance
        self.value = value

    def __str__(self) -> str:
        return f"ExperimentMetric({self.metric} - {self.instance} : {self.value})"
    
    def __repr__(self) -> str:
        return self.__str__()


class FlowCompletionTime(ExperimentMetric):
    """
    Time-bound data point metric represeting flow completion time.
    """
    def __init__(self, instance: str, value: float) -> None:
        super().__init__('fct', instance, value)


class RawQoe(ExperimentMetric):
    """
    Per-experiment data point metric represeting QoE as defined in the RobustMpc paper.
    """
    def __init__(self, instance: str, value: float) -> None:
        super().__init__('raw_qoe', instance, value)


class VmafQoe(ExperimentMetric):
    """
    Per-experiment data ponit metric representing QoE as defined in the Minerva paper.
    """
    def __init__(self, instance: str, value: float) -> None:
        super().__init__('vmaf_qoe', instance, value)


class Vmaf(ExperimentMetric):
    """ 
    Per-experimeent data point metric representing the average per-segment VMAF. 
    """
    def __init__(self, instance: str, value: float) -> None:
        super().__init__('vmaf', instance, value)


class Experiment:
    """
    Experiment data access structure. Gets loaded from a path and allows for metric parsing
    if the experiment instance had a successful run.
    """
    def __init__(self,
        video: str, 
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
        self.video = video

    def get_flow_capacity(self) -> List[float]: 
        """
        Extract flow capacity(in mbps float values) for all competing background 
        TCP traffic.
        """
        try:
            base_path  = str(Path(self.path).parents[0])
            all_values = []
            for file_ in Path(base_path).iterdir():
                file_path = str(file_)
                if "mbps_" in file_path:
                    with open(file_path, 'r') as f:
                        values = [float(l) for l in f.read().split('\n') if l != ""]
                        if max(values + [0]) > 10:
                            print(file_path)
                        all_values += values
            return all_values
        except:
            return []

    def get_flow_completion_times(self) -> List[float]: 
        """
        Extracts flow completion times(in seconds) for all competing background 
        TCP traffic.
        """
        base_path  = str(Path(self.path).parents[0])
        all_values = []
        for file_ in Path(base_path).iterdir():
            file_path = str(file_)
            if "fct_" in file_path:
                with open(file_path, 'r') as f:
                    values = [float(l) for l in f.read().split('\n') if l != ""]
                    all_values += values  
        return all_values

    def get_metrics(self) -> List[ExperimentMetric]:
        """
        Computes a list of per-experiment data point metrics.
        """
        try:
            segments = get_video_chunks(self.video) + 1
            with open(self.path, 'r') as graph_log:
                raw_qoe = defaultdict(lambda: defaultdict(int))
                vmaf_qoe = defaultdict(lambda: defaultdict(int))
                vmafd = defaultdict(lambda: defaultdict(int))
                rebuffd = defaultdict(lambda: defaultdict(int))
                
                def process(_input):
                    out = []
                    for line in _input.split('\n'):
                        vals = line.split('}{')
                        for i, val in enumerate(vals): 
                            val = '{' + val if i > 0 else val
                            val = val + '}' if i < len(vals) - 1 else val
                            out.append(val)
                    return out

                for line in process(graph_log.read()):
                    def proc_metric(curr_dict, metric):
                        if metric not in obj:
                            return
                        x = obj['x']
                        for name, value in obj[metric].items():
                            # not great
                            if x > 0 and x < segments - 2:
                                curr_dict[name][x] = value
                    
                    def proc_vmaf(curr_dict, vmaf, rebuff):
                        x = obj['x']
                        for name in vmaf.keys(): 
                            if x - 1 in vmaf[name]:
                                curr_dict[name][x] = (vmaf[name][x]
                                    - 100. * rebuff[name][x] 
                                    - 2.5 * abs(vmaf[name][x] - vmaf[name][x - 1]))
                            else:
                                curr_dict[name][x] = (vmaf[name][x]
                                    - 100. * rebuff[name][x]  
                                    - 2.5 * abs(vmaf[name][x] - 0))

                    obj = None
                    try:
                        obj = json.loads(line)
                    except:
                        pass
                    if obj:
                        proc_metric(vmafd, "vmaf")
                        proc_metric(rebuffd, "rebuffer")
                        proc_metric(raw_qoe, "raw_qoe")
                        
                        x = obj['x']
                        
                        try:
                            algo = list(obj[list(set(obj.keys()) - {'x'})[0]].keys())[0]
                            if x in vmafd[algo] and x in rebuffd[algo]:
                                proc_vmaf(vmaf_qoe, vmafd, rebuffd)
                        except:
                            pass

                out = []
                for name in raw_qoe.keys():
                    qoe_vals = list(raw_qoe[name].values())
                    total_qoe = sum(qoe_vals) / len(qoe_vals)

                    vmaf_vals = list(vmaf_qoe[name].values())
                    total_vmaf = sum(vmaf_vals) / len(qoe_vals)

                    vmaf_vals = list(vmafd[name].values())
                    total_rebuf = sum(vmaf_vals) / len(vmaf_vals)

                    out.append(RawQoe(name, total_qoe))
                    out.append(VmafQoe(name, total_vmaf))
                    out.append(Vmaf(name, total_rebuf))
                return out
        except FileNotFoundError as e:
            return []

    @staticmethod
    def from_json(json: JSONType) -> 'Experiment':
        """
        Loads experiment metadata from JSON format.
        """
        return Experiment(
            video = json['video'],
            path = json['path'],
            latency = json['latency'],
            extra = json['extra'],
            run_id = json['run_id'],
            bandwidth = json.get('bandwidth', None),
            trace = json.get('trace', None),
        )

    @property
    def json(self) -> JSONType:
        """
        Serialize experiment metadata into JSON format.
        """
        out = {
            'video' : self.video,
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
    """
    Save a list of experiment metadata in JSON format in file `path` with 
    one experiment metadata structure per line.
    """
    with open(str(Path(path) / 'experiments.txt'), "w") as log:
        for experiment in experiments:
            log.write(json.dumps(experiment.json))
            log.write('\n')

def load_experiments(path: str) -> List[Experiment]:
    """
    Load a list of experimental metadata from file `path`.
    """
    try:
        with open(str(Path(path) / 'experiments.txt'), "r") as log:
            contents = log.read()
            return [Experiment.from_json(json.loads(line)) 
                for line in contents.split('\n') if line != ""]
    except FileNotFoundError as e:
        return []


def generate_summary(path: str, experiments: List[Experiment]) -> None:
    """
    Generate a summary of ran experiments with their specific per-experiment metrics 
    saved in a single file.
    """
    with open(str(Path(path) / "log.txt"), "w") as summary:
        for experiment in experiments:  
            summary.write(f'> [{experiment.path}]')
            for metric in experiment.get_metrics():
                summary.write(f' {metric.metric}: {metric.value};')
            summary.write('\n') 
