import asyncio
import aiohttp

import argparse
import random
import logging


async def get(port: int) -> int:
    try:
        async with aiohttp.ClientSession() as session:
            link = f'https://localhost:{port}/traffic'
            async with session.get(link, ssl=False, timeout=5) as response:
                text = await response.text()
                return len(text)
    except Exception as e:
        logging.info(f'Exception during GET request: {e}')
        return 0


async def request(port: int) -> None:
     wait = random.random() * 2 
     await asyncio.sleep(wait)

     size = await get(port)
     logging.info(f'Served: {size} bytes')


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', metavar='-p', type=int, help='Port to make requests to.', default=8080)
    parser.add_argument('--connections', metavar='-c', default=50, type=int, help='Number parallel of connections.')
    args = parser.parse_args()

    while True:
        await asyncio.gather(*[
            request(args.port)
            for _ in range(args.connections)
        ])
    
if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
