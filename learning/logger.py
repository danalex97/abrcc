import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from typing import List

from constants import OUTPUT_SPACE  
from argparse import ArgumentParser, Namespace


class DecisionLogger:
    def __init__(self, path: str, read: bool = False):
        self.path: Path = str(Path(path) / 'decision.log')
        self.read: bool = read
        self.xs: List[List[float]] = [[] for _ in range(OUTPUT_SPACE)]
        if not read:
            self.log_file: file = open(self.path, 'w')

    def __del__(self):
        if not self.read:
            self.log_file.close()

    def log(self, vec: List[float]) -> None:
        self.log_file.write(f'{vec}\n')
        self.log_file.flush()

    def load(self) -> None:
        if not self.read:
            raise RuntimeError("Logger not initalized for reading.")
        self.xs = [[] for _ in range(OUTPUT_SPACE)]
        lines = 0
        with open(self.path, 'r') as log:
            for line in log.read().split('\n'):
                line = line.replace('nan', '0.')
                vec = None
                try:
                    vec = eval(line)
                except:
                    pass
                print(vec)
                if type(vec) == list:
                    for i, x in enumerate(vec):
                        self.xs[i].append(x + .1)
                    lines += 1
        print(f'Loaded {lines} lines')

    def plot(self):
        x = range(len(self.xs[0]))
        plt.stackplot(x, self.xs, labels = [f'action{i}' for i in range(OUTPUT_SPACE)])
        plt.legend(loc='upper left')
        plt.show()


if __name__ == "__main__":
    parser = ArgumentParser(description=f'Load log from path.')
    parser.add_argument('path', type=str, help='Log path.')
    args = parser.parse_args()
    
    logger = DecisionLogger(args.path, read=True)
    logger.load()
    logger.plot()
