import asyncio
import aiohttp
import argparse

import datetime
import json
import random
import re
import os
import sys
import time
import logging

import requests
import hashlib

from pathlib import Path
from typing import List, Optional, Set
from urllib3.exceptions import LocationParseError
from urllib.parse import urlparse, urljoin


class UrlUtilsMixin:
    @staticmethod
    def _normalize_link(link, root_url: str) -> str:
        try:
            parsed_url = urlparse(link)
        except ValueError:
            return None
        parsed_root_url = urlparse(root_url)

        if link.startswith("//"):
            return f"{parsed_root_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        if not parsed_url.scheme:
            return urljoin(root_url, link)
        return link

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        regex = re.compile(
            r'^(?:http|ftp)s?://' 
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  
            r'(?::\d+)?' 
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(regex, url) is not None


class Crawler(UrlUtilsMixin):
    """
    Crawler thar browses random pages from a given set of links and stores them into the 
    `cache` folder.
    """    
    _links: Set[str]
    _blacklist: Set[str]
   
    def __init__(self, links: int, parallel: int, cache: bool) -> None:
        self._links = set()
        self._blacklist = set()

        self._total_links = links
        self._parallel = parallel
        self._cache = cache
        if self._cache:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            self._cache_dir = str(Path(dir_path) / 'cache')
            os.system(f'mkdir -p {self._cache_dir}')
            
    async def _request(self, url: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    return await response.text()
        except:
            logging.debug("Exception on URL: %s" % url)
            return None

    def _is_blacklisted(self, url: str) -> bool:
        return url in self._blacklist

    def _should_accept_url(self, url: str) -> bool:
        return url and self._is_valid_url(url) and not self._is_blacklisted(url)

    def _extract_urls(self, body: str, root_url: str) -> List[str]:
        pattern = r"href=[\"'](?!#)(.*?)[\"'].*?"  
        urls = re.findall(pattern, str(body))

        normalize_urls = [self._normalize_link(url, root_url) for url in urls]
        filtered_urls = list(filter(self._should_accept_url, normalize_urls))

        return filtered_urls

    def load_config_file(self, file_path: str) -> None:
        """
        Load a configuration file with blacklisted urls and root urls for starting the 
        crawler.
        """
        with open(file_path, 'r') as config_file:
            config = json.load(config_file)
            for link in config['blacklisted_urls']:
                self._blacklist.add(link)
            for link in config["root_urls"]:
                self._links.add(link)

    async def browse(self) -> None:
        """
        Pop a single link from the current seed list and browser the page asynchronously. 
        The links found on the page will be added to the seed list. The browse function 
        will call itself after parsing one page.
        """
        if len(self._links) == 0:
            await asyncio.sleep(.1)
            await self.browse()
            return 

        link = self._links.pop()
        self._blacklist.add(link)
        
        try:
            logging.info(f"Visiting {link}")
            content = await self._request(link)
            if content is None:
                self._blacklist.remove(link)
                await self.browse()
                return 

            logging.info(f"Parsed {len(self._blacklist)} pages")
            logging.info(f"Content parsed @ {link}")
            
            if self._cache:
                hashed_link = hashlib.md5(str.encode(link)).hexdigest() 
                cache_file_path = str(Path(self._cache_dir) / hashed_link)
                if not os.path.isfile(cache_file_path):
                    logging.info(f"Caching {hashed_link}")
                    with open(cache_file_path, 'w') as f:
                        f.write(content)
            
            new_links = self._extract_urls(content, link)
            for link in new_links:
                self._links.add(link)
        
        except asyncio.TimeoutError:
            self._blacklist.remove(link)
            await self.browse()
            return

        if len(self._blacklist) < self._total_links:
            await self.browse()

    async def crawl(self):
        """
        Browse in parallel multiple pages until the needed number of browsed pages is reached.
        """
        await asyncio.gather(*[
            self.browse()
            for _ in range(self._parallel)
        ])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', metavar='-l', type=str, help='logging level', default='info')
    parser.add_argument('--config', metavar='-c', required=True, type=str, help='Config path.')
    parser.add_argument('--links', metavar='-t', default=1000, type=int, help='Links.')
    parser.add_argument('--parallel', metavar='-p', default=20, type=int, help='Number of conns.')
    parser.add_argument('--cache', action="store_true", help='Cache the pages.')
    args = parser.parse_args()

    level = getattr(logging, args.log.upper())
    logging.basicConfig(level=level)

    crawler = Crawler(args.links, args.parallel, args.cache)
    crawler.load_config_file(args.config)
    await crawler.crawl()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
