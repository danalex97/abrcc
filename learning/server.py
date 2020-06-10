from models import SimpleNNModel, Model
from constants import MAX_TARGET_BW, OUTPUT_SPACE 

from collections import defaultdict
from typing import Dict, List

from flask import Flask
from flask import request

import json
import signal
import sys



class Environment:
    instances: int
    inputs: Dict[int, List[int]]
    rewards: Dict[int, Dict[str, float]]
    actions: Dict[int, int]

    def __init__(self, instances: int = 2) -> None: 
        self.instaces = instances
        self.inputs = defaultdict(list)
        self.rewards = defaultdict(dict)
        self.actions = defaultdict(int)

    def add_input(self, index: int, input_vector: List[int]) -> None:
        self.inputs[index] = input_vector

    def add_reward(self, index: int, name: str, qoe: float) -> None:
        self.rewards[index][name] = qoe

    def add_action(self, index: int, action: int) -> None:
        self.actions[index] = action

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
            prediction: int = self.model.predict(input_vector)
            self.env.add_action(current_index, prediction)

            return str((prediction + 1) * MAX_TARGET_BW // OUTPUT_SPACE)

        @self.__app.route('/reward', methods=['POST'])
        def get_rewards():
            data = json.loads(request.data)

            name: str = str(data['name'])
            qoe: float = float(data['qoe'])
            index: int = int(data['index'])

            self.env.add_reward(index, name, qoe)
            if index > 1 and len(self.env.rewards[index]) > 1 and len(self.env.inputs[index]) > 0:
                self.model.update_replay_memory(
                    self.env.inputs[index - 1],
                    self.env.actions[index - 1],
                    self.env.rewards[index - 1],
                    self.env.inputs[index],
                )
                self.model.train()

            return "OK"

    @property
    def env(self) -> Environment:
        return self.__env

    def run(self) -> None:
        self.__app.run()        


if __name__ == '__main__':
    # Add signal handler for kills by experiment 
    def signal_handler(sig, frame):
        pass
    signal.signal(signal.SIGUSR1, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # start runner
    runner = Runner(Flask(__name__), SimpleNNModel()).run()
