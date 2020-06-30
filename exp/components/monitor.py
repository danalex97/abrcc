import asyncio
import json
import os

from pathlib import Path
from typing import List, Optional, Generator, Dict

from server.data import Metrics, Segment, Value
from server.server import post_after, post_after_async, Component, LogAccessMixin, JSONType
from abr.video import get_video_bit_rate, get_vmaf, get_chunk_size


TRAING_SERVER_PORT = 5000
PENALTY_REBUF = 4.3
PENALTY_QSWITCH = 1.0 
BOOST_QUALITY = 1.0 

K_in_M = 1000.0

REBUF_PENALITY_QOE = 100.
SWITCING_PENALITY_QOE = 2.5
SEGMENT_LENGTH = 4.0


class MetricsProcessor(LogAccessMixin):
    metrics: List[Metrics]
    timestamps: List[int]
    segments: List[Segment] 
    index: int 

    def __init__(self, video: str, logging: bool = False) -> None:
        super().__init__()
        
        self.video = video 
        self.metrics = []
        self.timestamps = [0]
        self.segments = []
        self.index = 1
        self.logging = logging
        self.vmaf_previous = 0

    def check_quality(self, segment: Segment) -> Optional[Dict[str, float]]:
        # Adjusts quality in case the rebuffering mechanism steps in
        last_segment = self.segments[-1]
        if segment.quality == last_segment.quality:
            return None
        if segment.index == last_segment.index and segment.timestamp > last_segment.timestamp:
            self.log(f'Correction detected @{segment.index}: '
                     f'{last_segment.quality} -> {segment.quality}')

            # update segment
            last_segment.quality = segment.quality
            self.segments[-1] = last_segment
            
            # update vmaf previous
            quality = get_video_bit_rate(self.video, segment.quality)
            vmaf = get_vmaf(self.video, self.index, quality)
            self.vmaf_previous = vmaf

            # Sending the metric updates
            return {
                'index' : self.index,
                'quality' : quality,
                'vmaf' : self.vmaf_previous,
                'timestamp' : segment.timestamp - self.timestamps[1], 
            }
        return None

    def advance(self, segment: Segment) -> Dict[str, float]:
        self.index += 1
        
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
        rebuffer = 0
        delay_snapshot = 100
        for time1, time2 in zip(player_times[:-1], player_times[1:]):
            real_time2 = time2.timestamp
            real_time1 = time1.timestamp

            player_time2 = time2.value
            player_time1 = time1.value
            
            player_diffence = (real_time2 - real_time1) - (player_time2 - player_time1)
            
            rebuffer += player_diffence / 1000.
            if rebuffer < 0:
                rebuffer = 0

        # Addjust for variance while treating all timestamps as a single one
        if len(player_times) > 1:
            t1 = player_times[0].timestamp
            t2 = player_times[-1].timestamp
            t3 = player_times[0].value
            t4 = player_times[-1].value
            once = ((t2 - t1) - (t4 - t3)) / 1000.
            maxerr = abs(once - rebuffer)
            rebuffer = rebuffer + maxerr
        
        # if buffer_levels are all much bigger then the player difference, 
        # we only encounter variance
        if len(buffer_levels) > 0 and min([l.value for l in buffer_levels]) >= rebuffer * delay_snapshot * 2:
            rebuffer = 0
        
        # ---------------------- Raw qoe logic --------------------------------
        quality = get_video_bit_rate(self.video, segment.quality)
        switch = (abs(get_video_bit_rate(self.video, self.segments[-1].quality) 
                    - get_video_bit_rate(self.video, self.segments[-2].quality))
            if len(self.segments) > 1 else 0)
      
        # Compute raw qoe
        raw_qoe = (quality / K_in_M * BOOST_QUALITY 
            - PENALTY_REBUF * rebuffer 
            - PENALTY_QSWITCH * switch / K_in_M)
     
        # ---------------------- Vmaf qoe logic --------------------------------
        # Get vmaf
        vmaf = get_vmaf(self.video, self.index, quality)
        
        # Compute vmaf qoe
        reward_vmaf = (vmaf 
            - REBUF_PENALITY_QOE * rebuffer 
            - SWITCING_PENALITY_QOE * abs(vmaf - self.vmaf_previous))
        self.vmaf_previous = vmaf
    

        # ---------------------- Bw estimation qoe -----------------------------
        # Current bw estimate - note this is an estiamte because the backend can transmit 
        # 2 segments at the same time: hence the actual value may be around 20% bigger/smaller
        segment_size = 8 * get_chunk_size(self.video, segment.quality, self.index - 1)
        time = timestamp - last_timestamp
        if time <= 0:
           time = 1
        bw = segment_size / time / 1000. # mbps

        # Appending the segment
        self.segments.append(segment)
        
        # Sending the metrics
        return {
            'index' : self.index,
            'quality' : quality,
            'rebuffer' : rebuffer, 
            'raw_qoe' : raw_qoe,
            'vmaf' : vmaf,
            'vmaf_qoe' : reward_vmaf,
            'bw' : bw,
            'timestamp' : timestamp - self.timestamps[1], 
        }
    
    def compute_qoe(self, metrics: Metrics) -> Generator[Dict[str, float], None, None]: 
        self.metrics.append(metrics)
        for segment in metrics.segments:
            if segment.index >= self.index + 1 and segment.loading:
                if self.logging:
                    self.log('Current segment: ', segment)
                yield self.advance(segment)
            elif segment.loading:
                maybe_check_quality = self.check_quality(segment)
                if maybe_check_quality is not None:
                    self.log('Quality check successful: ', maybe_check_quality)


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
        training: bool = False,
        log_to_file: bool = True,
    ) -> None:
        super().__init__()

        self.path = path / f'{name}_metrics.log' 
        self.port = port
        self.name = name
        self.processor = MetricsProcessor(video)

        self.plot = plot
        self.request_port = request_port
        self.log_to_file = log_to_file
        self.training = training

    async def log_path(self, metrics: Metrics) -> None:
        if self.log_to_file:
            with open(self.path, 'a') as f:
                f.write(json.dumps(metrics.json))
                f.write('\n')

    async def advance(self, processed_metrics: Dict[str, float]) -> None:
        if not self.plot:
            return 
        
        rebuffer = processed_metrics.get('rebuffer', None)
        quality = processed_metrics.get('quality', None)
        raw_qoe = processed_metrics.get('raw_qoe', None)
        vmaf = processed_metrics.get('vmaf', None)
        vmaf_qoe = processed_metrics.get('vmaf_qoe', None)
        bw = processed_metrics.get('bw', None)
        idx = processed_metrics['index']

        port = self.request_port
        timestamp = int(processed_metrics['timestamp']/1000)
        
        make_value = lambda value: {
            'name': self.name, 'timestamp': timestamp, 'value': Value(value, idx).json
        }
        make_bw = lambda value: {
            'name': self.name, 'timestamp': timestamp, 'value': Value(value, timestamp).json
        }
         
        if rebuffer is not None: post_after_async(make_value(rebuffer), 0, "/rebuffer", port=port)
        if quality is not None:  post_after_async(make_value(quality), 0, "/quality", port=port)
        if raw_qoe is not None:  post_after_async(make_value(raw_qoe), 0, "/raw_qoe", port=port)
        if vmaf is not None:     post_after_async(make_value(vmaf), 0, "/vmaf", port=port)
        if vmaf_qoe is not None: post_after_async(make_value(vmaf_qoe), 0, "/vmaf_qoe", port=port)
        if bw is not None:       post_after_async(make_bw(bw), 0, "/bw", port=port)

        if self.training:
            await post_after(
                data = {
                    'name' : self.name,
                    'qoe' : vmaf_qoe,
                    'index' : idx,
                }, 
                wait = 0,
                resource = '/reward',
                port = TRAING_SERVER_PORT,
                ssl = False, 
            )

    async def compute_qoe(self, metrics: Metrics) -> None: 
        for processed_metrics in self.processor.compute_qoe(metrics): 
            await self.advance(processed_metrics)
    
    async def process(self, json: JSONType) -> JSONType:
        if 'json' in json:
            json = json['json']
        if 'stats' in json:
            metrics = Metrics.from_json(json['stats'])
            self.log('Processing ', metrics)
            asyncio.gather(*[
                self.log_path(metrics),
                self.compute_qoe(metrics),
            ])
        if 'complete' in json:
            post_after_async(json, 0, "/complete", port=self.port) 
        return 'OK'
