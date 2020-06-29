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


