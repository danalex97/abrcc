import asyncio
import json
from pathlib import Path
from typing import List

from data import Metrics, Segment, Value
from server import post_after, Component, JSONType


PENALTY_REBUF = 4.3
PENALTY_QSWITCH = 1.0 
BOOST_QUALITY = 1.0 

K_in_M = 1000.0


class Monitor(Component):
    path: Path
    metrics: List[Metrics]
    timestamps: List[int]
    segments: List[Segment] 
    index: int 

    def __init__(self, path: Path) -> None:
        self.path = path 
        self.metrics = []
        self.timestamps = [0]
        self.segments = []
        self.index = 1

        # [TODO] remove hardcoding
        self.qualities = [300, 750, 1200, 1850, 2850, 4300]

    async def log_path(self, metrics: Metrics) -> None:
        with open(self.path, 'a') as f:
            f.write(json.dumps(metrics.json))
            f.write('\n')

    async def advance(self, segment: Segment) -> None:
        self.index += 1
        self.segments.append(segment)
        
        # We synchronize on the timestamp of segments getting loaded
        last_timestamp = self.timestamps[-1]
        timestamp = segment.timestamp 
        self.timestamps.append(timestamp)
        
        # Compute player times and buffer levels
        in_interval = lambda l: [v for v in l if 
            v.timestamp > last_timestamp and v.timestamp <= timestamp]
        get_values = lambda l: sorted(in_interval(sum(l, [])), key=lambda x: x.timestamp)

        player_times  = get_values(m.playerTime for m in self.metrics)
        buffer_levels = get_values(m.bufferLevel for m in self.metrics)
        
        # Compute quality, rebuffering time and difference in quality switches
        rebuffer = 0 # in s
        for time1, time2 in zip(player_times[:-1], player_times[1:]):
            real_time2 = time2.timestamp
            real_time1 = time1.timestamp

            player_time2 = time2.value
            player_time1 = time1.value
            
            player_diffence = (real_time2 - real_time1) - (player_time2 - player_time1)
            rebuffer += max(0, player_diffence) / 1000.

        # if buffer_levels are all much bigger then the player difference, we only encounter variance
        if len(buffer_levels) > 0 and min([l.value for l in buffer_levels]) >= rebuffer * 1500:
            rebuffer = 0

        quality = self.qualities[segment.quality]
        switch = (abs(self.qualities[self.segments[-1].quality] - self.qualities[self.segments[-2].quality])
            if len(self.segments) > 1 else 0)
       
        # Compute qoe
        qoe = (quality / K_in_M * BOOST_QUALITY 
            - PENALTY_REBUF * rebuffer 
            - PENALTY_QSWITCH * switch / K_in_M)
       
        await asyncio.gather(*[
            post_after(Value(rebuffer, self.index).json, 0, "/rebuffer"),
            post_after(Value(switch, self.index).json, 0, "/switch"),
            post_after(Value(quality, self.index).json, 0, "/quality"),
            post_after(Value(qoe, self.index).json, 0, "/qoe"),
        ])
       

    async def compute_qoe(self, metrics: Metrics) -> None: 
        self.metrics.append(metrics)
        for segment in metrics.segments:
            if segment.index == self.index + 1 and segment.loading:
                print(segment)
                await self.advance(segment)
                
    async def process(self, json: JSONType) -> JSONType:
        metrics = Metrics.from_json(json['stats'])
        asyncio.gather(*[
            self.log_path(metrics),
            self.compute_qoe(metrics),
        ])
        return 'OK'
