import asyncio
import aiohttp
import os

import argparse
import random
import logging
import time
import functools

from typing import Optional, TextIO


class LazyFileWriter:
    def __init__(self, path: str) -> None:
        os.system(f"touch -p {path}")
        self.log = open(path, 'w')
        self.values = []

    def write(self, value: int) -> None:
        self.values.append(value)
        if len(self.values) > 100:
            self.flush()

    def flush(self) -> None:
        for value in self.values:
            self.log.write(f"{value}\n")
        self.log.flush()
        self.values = []


    def __del__(self) -> None:
        self.log.close()
    

class TimedTCPConnector(aiohttp.TCPConnector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connection_started_time = None

    @property 
    def connection_started_time(self) -> Optional[float]:
        return self._connection_started_time
    
    async def _create_connection(self, *args, **kwargs) -> aiohttp.ClientSession:
        self._connection_started_time = time.time()
        return await super()._create_connection(*args, **kwargs)


async def get(port: int, time_log: Optional[LazyFileWriter]) -> int:
    try:
        connector = TimedTCPConnector()
        async with aiohttp.ClientSession(connector=connector) as session:
            link = f'https://localhost:{port}/traffic'
            async with session.get(link, ssl=False, timeout=10) as response:
                text = await response.text()
                started_time_connection = connector.connection_started_time 
                if started_time_connection is not None:
                    current_time = time.time()
                    connection_time_ms = (current_time - started_time_connection) * 1000
                    logging.info(f'Flow completion time: {connection_time_ms} ms')
                    if time_log:
                        time_log.write(connection_time_ms)
                return len(text)
    except Exception as e:
        if time_log:
            time_log.flush()
        logging.info(f'Exception during GET request: {e}')
        return 0


async def request(port: int, time_log: Optional[LazyFileWriter] = None) -> None:
     wait = random.random() * 2 
     await asyncio.sleep(wait)

     size = await get(port, time_log)
     logging.info(f'Served: {size} bytes')


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port to make requests to.', default=8080)
    parser.add_argument('--connections', metavar='-c', default=50, type=int, help='Number parallel of connections.')
    parser.add_argument('--time-log', metavar='-l', type=str, help='Location for time log.')
    args = parser.parse_args()

    if args.time_log is not None:
        time_log = LazyFileWriter(args.time_log)
    else:
        time_log = None

    while True:
        await asyncio.gather(*[
            request(args.port, time_log)
            for _ in range(args.connections)
        ])
    
if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
