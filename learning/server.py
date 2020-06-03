from abc import abstractmethod, ABC
from collections import defaultdict
from typing import Dict, List

from flask import Flask
from flask import request

import json


class Model(ABC):
    @abstractmethod
    def predict(self, input_vector: List[int]) -> int:
        pass


class DummyModel(Model):
    def predict(self, input_vector: List[int]) -> int:
        return 1


class Environment:
    instances: int
    inputs: Dict[int, List[int]]
    rewards: Dict[int, Dict[str, float]]

    def __init__(self, instances: int = 2) -> None: 
        self.instaces = instances
        self.inputs = defaultdict(list)
        self.rewards = defaultdict(dict)

    def add_input(self, index: int, input_vector: List[int]) -> None:
        self.inputs[index] = input_vector

    def add_reward(self, index: int, name: str, qoe: float) -> None:
        self.rewards[index][name] = qoe

    def reset(self) -> None:
        self.inputs = defaultdict(list)
        self.rewards = defaultdict(dict)


class Runner:
    def __init__(self, app: Flask, model: Model) -> None:
        self.__app = app
        self.__env = Environment()
        self.model = model
    
        @self.__app.route('/target_bandwidth')
        def get_target_bandwidth():
            avg_bandwidth: int = int(request.args.get('avg_bandwidth'))
            current_bandwidth: int = int(request.args.get('current_bandwidth'))
            last_buffer: int = int(request.args.get('last_buffer'))
            last_rtt: int = int(request.args.get('last_rtt')) 

            vmafs: List[List[int]] = eval(request.args.get('vmafs'))
            sizes: List[List[int]] = eval(request.args.get('sizes'))

            current_quality: int = int(request.args.get('current_quality'))
            current_index: int = int(request.args.get('current_index'))
            current_vmaf: int = vmafs[0][current_quality - 1]
            current_size: int = sizes[0][current_quality - 1]

            input_vector: List[int] = [
                avg_bandwidth, current_bandwidth, last_buffer, 
                last_rtt, current_vmaf, current_size,
            ]
            input_vector += sum(vmafs, [])
            input_vector += sum(sizes, [])
            
            if current_index in self.env.inputs:
                # We already have the current index, so it means that we 
                # are running a new experiment
                self.__env.reset()

            self.env.add_input(current_index, input_vector)
            return str(self.model.predict(input_vector))

        @self.__app.route('/reward', methods=['POST'])
        def get_rewards():
            data = json.loads(request.data)

            name: str = str(data['name'])
            qoe: float = float(data['qoe'])
            index: int = int(data['index'])
            
            self.env.add_reward(index, name, qoe)
            return "OK"

    @property
    def env(self) -> Environment:
        return self.__env

    def run(self) -> None:
        self.__app.run()        


if __name__ == '__main__':
    runner = Runner(Flask(__name__), DummyModel()).run()
