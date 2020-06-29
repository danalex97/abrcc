import asyncio
import aiounittest
import unittest
import json

from typing import List
from pathlib import Path
from unittest.mock import MagicMock

from server.server import JSONType
from server.data import Metrics
from components import monitor
from collections import defaultdict


def get_replay_log(log_path: str) -> List[JSONType]:
    with open(log_path, 'r') as f:
        return list(map(json.loads, f.read().split('\n')[:-1]))


class TestMonitor(monitor.Monitor):
    async def log_path(self, metrics: Metrics) -> None:
        pass 


class MonitorTests(aiounittest.AsyncTestCase):
    def setUp(self):
        print()
        print('Test setup...')
        self.monitor = TestMonitor(
            video = 'test',
            path =  Path(), 
            name = 'algo',
            plot = True, 
            request_port = None,
            port = None,
            training = False,
            log_to_file = False,
        )
        print('Test setup done.')
   
    async def test_rebuffer_values_for_log_with_rebuffering(self):
        """
        Test that all rebuffer values have a difference of at most 1 between different tests.
        """
        def post_after_async(data: JSONType, wait: int, resource: str, **kwargs) -> None:
            if 'rebuffer' in resource:
                index = data['value']['timestamp']
                value = data['value']['value']
                
                if index == 7:
                    self.assertAlmostEqual(value, 1.936, places=1)
                elif index == 8:
                    self.assertAlmostEqual(value, 4.345, places=1)
                else:
                    self.assertEquals(value, 0)
                    

        monitor.get_video_bit_rate = lambda _x, _y: 0
        monitor.get_chunk_size     = lambda _x, _y, _z: 1
        monitor.get_vmaf           = lambda _x, _y, _z: 1
        monitor.post_after_async   = post_after_async 
        
        for entry in get_replay_log(
            str(Path('components') / 'tests' / 'logs' / 'rebuffers.log')
        ):
            await self.monitor.process({'stats' : entry})

    async def test_rebuffer_values_for_no_rebuffering_logs(self):
        """
        Test that all rebuffer values are 0 for a log with no rebuffering.
        """
        def post_after_async(data: JSONType, wait: int, resource: str, **kwargs) -> None:
            if 'rebuffer' in resource:
                index = data['value']['timestamp']
                value = data['value']['value']
                self.assertEquals(value, 0)
                    

        monitor.get_video_bit_rate = lambda _x, _y: 0
        monitor.get_chunk_size     = lambda _x, _y, _z: 1
        monitor.get_vmaf           = lambda _x, _y, _z: 1
        monitor.post_after_async   = post_after_async 
        
        for entry in get_replay_log(
            str(Path('components') / 'tests' / 'logs' / 'no_rebuffers.log')
        ):
            await self.monitor.process({'stats' : entry})

    async def test_qualities_correspond_to_last_log_value(self):
        log = get_replay_log(
            str(Path('components') / 'tests' / 'logs' / 'rebuffers.log')
        )
        segments = sum((entry['segments'] for entry in log), [])
        qualities = {}
        MESSAGES = 30
        self.messages = 0
        
        def post_after_async(data: JSONType, wait: int, resource: str, **kwargs) -> None:
            if 'quality' in resource:
                self.messages += 1
                index = data['value']['timestamp']
                value = data['value']['value']
                ts = data['timestamp']
                if index not in qualities or qualities[index][1] < ts:
                    qualities[index] = value, ts

                if self.messages == MESSAGES:
                    print('Checking...')
                    for index, value_ts in qualities.items():
                        value, ts = value_ts
                        quality, timestamp = None, -1
                        for segment in segments:
                            if segment['index'] == index:
                                if segment['timestamp'] > timestamp:
                                    quality, timestamp = segment['quality'], segment['timestamp']
                        self.assertEquals(value, quality)

        monitor.get_video_bit_rate = lambda _x, quality: quality
        monitor.get_chunk_size     = lambda _x, _y, _z: 100
        monitor.get_vmaf           = lambda _x, _y, _z: 1
        monitor.post_after_async   = post_after_async 
              
        for entry in log:
            await self.monitor.process({'stats' : entry})

    async def test_vmafs_correspond_to_last_log_value(self):
        log = get_replay_log(
            str(Path('components') / 'tests' / 'logs' / 'rebuffers.log')
        )
        segments = sum((entry['segments'] for entry in log), [])
        qualities = {}
        MESSAGES = 30
        self.messages = 0
        
        def post_after_async(data: JSONType, wait: int, resource: str, **kwargs) -> None:
            if 'vmaf' in resource:
                self.messages += 1
                index = data['value']['timestamp']
                value = data['value']['value']
                ts = data['timestamp']
                if index not in qualities or qualities[index][1] < ts:
                    qualities[index] = value, ts

                if self.messages == MESSAGES:
                    print('Checking...')
                    for index, value_ts in qualities.items():
                        value, ts = value_ts
                        quality, timestamp = None, -1
                        for segment in segments:
                            if segment['index'] == index:
                                if segment['timestamp'] > timestamp:
                                    quality, timestamp = segment['quality'], segment['timestamp']
                        self.assertEquals(value, quality)

        monitor.get_video_bit_rate = lambda _x, quality: quality
        monitor.get_chunk_size     = lambda _x, _y, _z: 100
        monitor.get_vmaf           = lambda _x, _y, quality: quality
        monitor.post_after_async   = post_after_async 
              
        for entry in log:
            await self.monitor.process({'stats' : entry})
