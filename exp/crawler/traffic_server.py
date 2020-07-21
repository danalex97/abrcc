from server.server import Server, Component
from server.data import JSONType

from os import listdir
from os.path import isfile, join
from pathlib import Path
from typing import List

import random
import argparse
import os
import logging


def get_file_size(file_path: str) -> int:
    stat_info = os.stat(file_path)
    return stat_info.st_size / 1024 / 1024


class RandomPageProcessor(Component):
    cache: List[str]
    
    def __init__(self):
        super().__init__()
        self.cache = []
    
    def load_cache(self, cache_size: int) -> None: 
        dir_path = os.path.dirname(os.path.realpath(__file__))
        cache_dir = str(Path(dir_path) / 'cache')

        cache_files = [f for f in listdir(cache_dir) if isfile(join(cache_dir, f))]
        random.shuffle(cache_files)
        
        total_size = 0
        files = 0
        for cache_file_base in cache_files:
            cache_file = str(Path(cache_dir) / cache_file_base)
            total_size += get_file_size(cache_file) 
            files += 1

            with open(cache_file, 'r') as f:
                content = f.read()
                self.cache.append(content)

            if total_size > cache_size:
                break
        self.log(f'Loaded {files} files of size {total_size} MB')
        
    async def serve_random_content(self) -> JSONType:
        return random.choice(self.cache)

    async def process(self, _: JSONType) -> JSONType:
        return await self.serve_random_content()


def main(args: argparse.Namespace) -> None:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    logs_dir = str(Path(dir_path) / 'logs')
    os.system(f'mkdir -p {logs_dir}')

    processor = RandomPageProcessor()

    server = Server('traffic', args.port)
    server.add_get('/traffic', processor)
    server.add_logger('traffic', str(Path(logs_dir) / f'traffic{args.port}.log'))

    processor.load_cache(args.cache)

    server.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port.', default=8080)
    parser.add_argument('--cache', metavar='-c', type=int, help='Cache size in mbit.', default=100)
    main(parser.parse_args()) 
