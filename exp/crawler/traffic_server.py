import os.path, sys # need this to be able to import server.server for priveleged processes
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

from server.server import Server, Component
from server.data import JSONType

from os import listdir
from os.path import isfile, join
from pathlib import Path
from typing import List

import math
import random
import argparse
import os
import logging
import time
#import seaborn as sns
#import matplotlib.pyplot as plt


def get_file_size(file_path: str) -> int:
    stat_info = os.stat(file_path)
    return stat_info.st_size / 1024 / 1024


class RandomPageProcessor(Component):
    cache: List[str]
    
    def __init__(self, max_load: int):
        super().__init__()
        self.cache = []
        self.active = 0
        self.start_time = None
        self.max_load = max_load

    def load_cache(self, cache_size: int, adjust: bool = False) -> None: 
        neg_exp = lambda: -math.log(1 - (1 - math.exp(-1)) * random.random()) / 1
        dir_path = os.path.dirname(os.path.realpath(__file__))
        cache_dir = str(Path(dir_path) / 'cache')

        cache_files = [f for f in listdir(cache_dir) if isfile(join(cache_dir, f))]
        random.shuffle(cache_files)
        
        total_size = 0
        files = 0
        sizes = []
        for cache_file_base in cache_files:
            cache_file = str(Path(cache_dir) / cache_file_base)
            
            file_size = get_file_size(cache_file)

            if adjust:
                # adjust the traffic distribution by composing it with a 
                # negative exponential ditribution with lambda 1 with an 
                # avrage size 400kb files
                if neg_exp() * 400 < file_size * 1000:
                    continue

            sizes.append(file_size * 1000)
            total_size += file_size 

            files += 1
            with open(cache_file, 'r') as f:
                content = f.read()
                self.cache.append(content)

            if total_size > cache_size:
                break
        #sns.distplot(sizes, kde=False, rug=False)
        #plt.ylabel('flows')
        #plt.xlabel('flow size(kb)')
        #plt.show()
        self.log(f'Loaded {files} files of size {total_size} MB')
        
    async def serve_random_content(self) -> JSONType:
        content = random.choice(self.cache)
        load = 0
        if self.start_time is None:
            self.start_time = time.time()
        else:
            load = self.active / (time.time() - self.start_time)
            self.log('Current load:' , load)
        if load > self.max_load:
            return ""
        else:
            self.active += len(content) / 1024 / 1024
        return content

    async def process(self, _: JSONType) -> JSONType:
        return await self.serve_random_content()


def main(args: argparse.Namespace) -> None:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    logs_dir = str(Path(dir_path) / 'logs')
    os.system(f'mkdir -p {logs_dir}')

    processor = RandomPageProcessor(args.max_load)

    server = Server('traffic', args.port)
    server.add_get('/traffic', processor)
    server.add_logger('traffic', str(Path(logs_dir) / f'traffic{args.port}.log'))

    processor.load_cache(args.cache, args.light)

    server.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    parser.add_argument('--cache', metavar='-c', type=int, help='Cache size in MB.', default=100)
    parser.add_argument('--max-load', type=int, help='Max load in mbps.', default=.5)
    parser.add_argument('--light', action='store_true', help='Lighter traffic.')
    main(parser.parse_args()) 
