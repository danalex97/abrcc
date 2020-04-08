from pathlib import Path
from typing import List, Dict

import os
import json


__JSON_CACHE = {}
def __get_json(video: str) -> Dict[int, List[Dict[str, float]]]:
    global __JSON_CACHE

    if video not in __JSON_CACHE:
        directory = Path(os.path.dirname(os.path.realpath(__file__)))
        directory = directory / '..'  / '..' / 'quic'
        json_path = str(directory / 'sites' / video / 'config.json')
        print(json_path)

        info = {}
        with open(json_path, 'r') as json_file:
            text = json_file.read()
            raw_son = json.loads(text)
            
            for son in raw_son["video_paths"]:
                info[son["quality"]] = son["info"]
            __JSON_CACHE[video] = info

    return __JSON_CACHE[video]
    

def get_video_chunks(video: str) -> int:
    return len(list(__get_json(video).values())[0]) 


__BITRATE_CACHE = {}
def get_video_bit_rate(video: str, quality: int) -> int:
    global __BITRATE_CACHE 
    if video not in __BITRATE_CACHE:
        vals = list(__get_json(video).keys())
        __BITRATE_CACHE[video] = list(sorted(vals))
    return __BITRATE_CACHE[video][quality]


def get_chunk_size(video: str, quality: int, index: int) -> int:
    if index > get_video_chunks(video) or index < 0:
        return 0
    return __get_json(video)[get_video_bit_rate(video, quality)][index - 1]["size"]


def get_max_video_bit_rate(video: str) -> int:
    return max(list(__get_json(video).keys()))


def get_nbr_video_bit_rate(video: str) -> int:
    return len(list(__get_json(video).keys()))


def __get_start_time(video: str, quality: int, index: int) -> float:
    if index > get_video_chunks(video) or index < 0:
        return 0
    return __get_json(video)[get_video_bit_rate(video, quality)][index - 1]["start_time"]


def get_chunk_time(video: str, quality: int, index: int) -> float:
    if index > get_video_chunks(video) or index < 0:
        return 0
    if index == get_video_chunks(video):
        index -= 1
    t1 = __get_start_time(video, quality, index)
    t2 = __get_start_time(video, quality, index + 1)  
    return t2 - t1


def get_vmaf(video: str, index: int, bitrate: int) -> float:
    if index > get_video_chunks(video) or index < 0:
        return 0
    return __get_json(video)[get_video_bit_rate(video, quality)][index - 1]["vmaf"]
