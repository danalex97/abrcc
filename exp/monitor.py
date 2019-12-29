import asyncio
import json
from pathlib import Path

from data import Metrics
from server import Component, JSONType


class Monitor(Component):
    def __init__(self, path: Path) -> None:
       self.path = path 
  
    async def log_path(self, metrics: Metrics) -> None:
        with open(self.path, 'a') as f:
            f.write(json.dumps(metrics.json))
            f.write('\n')

    async def process(self, json: JSONType) -> JSONType:
        metrics = Metrics.from_json(json['stats'])
        asyncio.gather(*[
            self.log_path(metrics),
        ])
        return 'OK'
