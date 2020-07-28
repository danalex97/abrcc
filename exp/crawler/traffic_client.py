import asyncio
import aiohttp
import os

import argparse
import random
import logging
import time
import traceback
import functools

from typing import Optional, TextIO


WAIT_TIME = 2


class FileWriter:
    def __init__(self, path: str) -> None:
        os.system(f"touch -p {path}")
        self.log = open(path, 'w')

    def write(self, value: int) -> None:
        self.log.write(f"{value}\n")
        self.log.flush()

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


ok_gets = 0
er_gets = 0

async def get(port: int, time_log: Optional[FileWriter]) -> int:
    global ok_gets, er_gets
    try:
        connector = TimedTCPConnector()
        async with aiohttp.ClientSession(connector=connector) as session:
            link = f'https://localhost:{port}/traffic'
            async with session.get(link, ssl=False, timeout=15) as response:
                text = await response.text()
            started_time_connection = connector.connection_started_time 
            if started_time_connection is not None:
                current_time = time.time()
                connection_time_ms = (current_time - started_time_connection) * 1000
                logging.info(f'Flow completion time: {connection_time_ms} ms')
                if time_log:
                    time_log.write(connection_time_ms)
            ok_gets += 1
            return len(text)
    except Exception as e:
        er_gets += 1
        err_rate = er_gets/(ok_gets+er_gets)
        logging.info(f'Finished gets: {ok_gets}') 
        logging.info(f'Error rate: {err_rate}') 
        logging.info(f'Exception during GET request: {e}')
        logging.info(f'Traceback: {traceback.format_exc()}')
        return 0


async def request(port: int, time_log: Optional[FileWriter] = None) -> None:
     wait = random.random() * WAIT_TIME 
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
        time_log = FileWriter(args.time_log)
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
