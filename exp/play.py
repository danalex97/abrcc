import asyncio
import json

from argparse import ArgumentParser
from typing import List

from server import post_after
from data import Metrics 


async def send_after(metrics: Metrics, port: int, timestamp: int) -> None:
    await post_after(
        data     = {'stats' : metrics.json},
        wait     = timestamp,
        resource = "/metrics",
        port     = port,
    )


async def consume(metrics: List[Metrics], port: int, real_time: bool) -> None:
    if real_time:
        await asyncio.gather(*[
            send_after(m, port, m.timestamp) for m in metrics
        ])
    else:
        await asyncio.gather(*[
            send_after(m, port, i * 10) for i, m in enumerate(metrics)
        ])


if __name__ == "__main__":
    parser = ArgumentParser(description='')
    parser.add_argument('path', type=str, help='Path of the log trace to play.')
    parser.add_argument('--port', type=int, default=8080, help='Port of running server(default 8008).')
    parser.add_argument('--real-time', action='store_true', dest='real_time', help='Play in real time.')
    args = parser.parse_args()

    with open(args.path) as f:
        lines   = f.read().split('\n')
        metrics = [Metrics.from_json(json.loads(l)) for l in lines if l != ""] 
        print(f'Playing log with {len(metrics)} entries...')

        loop = asyncio.get_event_loop()
        loop.run_until_complete(consume(metrics, args.port, args.real_time))
        print('Log played.')
