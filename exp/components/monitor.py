import asyncio
import json
import os

from pathlib import Path
from typing import List, Optional, Generator, Dict

from server.data import Metrics, Segment, Value
from server.server import post_after, post_after_async, Component, JSONType
from abr.video import get_video_bit_rate, get_vmaf, get_chunk_size


PENALTY_REBUF = 4.3
PENALTY_QSWITCH = 1.0 
BOOST_QUALITY = 1.0 

K_in_M = 1000.0

REBUF_PENALITY_QOE = 25
SWITCING_PENALITY_QOE = 2.5
SEGMENT_LENGTH = 4.0


class MetricsProcessor:
    metrics: List[Metrics]
    timestamps: List[int]
    segments: List[Segment] 
    index: int 

    def __init__(self, video: str, logging: bool = False) -> None:
        self.video = video 
        self.metrics = []
        self.timestamps = [0]
        self.segments = []
        self.index = 1
        self.logging = logging
        self.vmaf_previous = 0

    def advance(self, segment: Segment) -> None:
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

        # [TODO] See rebuffer time issue
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

        quality = get_video_bit_rate(self.video, segment.quality)
        switch = (abs(get_video_bit_rate(self.video, self.segments[-1].quality) 
                    - get_video_bit_rate(self.video, self.segments[-2].quality))
            if len(self.segments) > 1 else 0)
       
        # Compute raw qoe
        raw_qoe = (quality / K_in_M * BOOST_QUALITY 
            - PENALTY_REBUF * rebuffer 
            - PENALTY_QSWITCH * switch / K_in_M)
     
        # Get vmaf
        vmaf = get_vmaf(self.video, self.index, quality)
        
        # [TODO] Check this is ok
        # Compute vmaf qoe
        reward_vmaf = (vmaf 
            - REBUF_PENALITY_QOE * rebuffer / 1000. 
            - SWITCING_PENALITY_QOE * abs(vmaf - self.vmaf_previous))
        self.vmaf_previous = vmaf
    
        # Current bw estimate - note this is an estiamte because the backend can transmit 
        # 2 segments at the same time: hence the actual value may be around 20% bigger/smaller
        # [TODO] this can be fixed by using e.g. progress segments 
        segment_size = 8 * get_chunk_size(self.video, segment.quality, self.index - 1)
        time = timestamp - last_timestamp
        # [TODO] can I do something smarted
        if time <= 0:
           time = 1
        bw = segment_size / time / 1000. # mbps

        return {
            'index' : self.index,
            'quality' : quality,
            'rebuffer' : rebuffer, 
            'raw_qoe' : raw_qoe,
            'vmaf' : vmaf,
            'vmaf_qoe' : reward_vmaf,
            'bw' : bw,
            # [TODO] do this properly
            'timestamp' : timestamp - self.timestamps[1], 
            # So we (approx) align metrics that are per-timestamp
        }
    
    def compute_qoe(self, metrics: Metrics) -> Generator[Dict[str, float], None, None]: 
        self.metrics.append(metrics)
        for segment in metrics.segments:
            if segment.index >= self.index + 1 and segment.loading:
                if self.logging:
                    print(segment)
                yield self.advance(segment)


class Monitor(Component):
    video: str
    path: Path
    name: str
    processor: MetricsProcessor

    def __init__(self, 
        video: str,
        path: Path, 
        name: str,
        plot: bool = False,
        request_port: Optional[int] = None,
        port: Optional[int] = None,
    ) -> None:
        self.path = path / f'{name}_metrics.log' 
        self.port = port
        self.name = name
        self.processor = MetricsProcessor(video)

        self.plot = plot
        self.request_port = request_port

    async def log_path(self, metrics: Metrics) -> None:
        with open(self.path, 'a') as f:
            f.write(json.dumps(metrics.json))
            f.write('\n')

    async def advance(self, processed_metrics: Dict[str, float]) -> None:
        if not self.plot:
            return 

        rebuffer = processed_metrics['rebuffer']
        quality = processed_metrics['quality']
        raw_qoe = processed_metrics['raw_qoe']
        vmaf = processed_metrics['vmaf']
        vmaf_qoe = processed_metrics['vmaf_qoe']
        bw = processed_metrics['bw']
        idx = processed_metrics['index']
        port = self.request_port
        timestamp = int(processed_metrics['timestamp']/1000)

        make_value = lambda value: {'name': self.name, 'value': Value(value, idx).json}
        make_bw = lambda value: {'name': self.name, 'value': Value(value, timestamp).json}
        post_after_async(make_value(rebuffer), 0, "/rebuffer", port=port),
        post_after_async(make_value(quality), 0, "/quality", port=port),
        post_after_async(make_value(raw_qoe), 0, "/raw_qoe", port=port),
        post_after_async(make_value(vmaf), 0, "/vmaf", port=port),
        post_after_async(make_value(vmaf_qoe), 0, "/vmaf_qoe", port=port),
        post_after_async(make_bw(bw), 0, "/bw", port=port),
    
    async def compute_qoe(self, metrics: Metrics) -> None: 
        for processed_metrics in self.processor.compute_qoe(metrics): 
            await self.advance(processed_metrics)
    
    async def process(self, json: JSONType) -> JSONType:
        if 'stats' in json:
            metrics = Metrics.from_json(json['stats'])
            asyncio.gather(*[
                self.log_path(metrics),
                self.compute_qoe(metrics),
            ])
        if 'complete' in json:
            post_after_async(json, 0, "/complete", port=self.port) 
        return 'OK'
