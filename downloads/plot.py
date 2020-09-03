import matplotlib.pyplot as plt

from argparse import ArgumentParser, Namespace
from video_downloader import run_cmd
from typing import Dict

import os
import json


def process_info(
    info: Dict[str, float],
    quality: int,
    segment: int,
    tracks_path: str,
) -> Dict[str, float]:
    quality = int(run_cmd(
        f"du -b '{tracks_path}/video_{quality}/{segment}.m4s' | cut -f1"
    ))
    info['size'] = quality
    return info


def main(args: Namespace) -> None:
    text = {
        'got' : "Game of Thrones",
        'guard' : "Guardians of the Galaxy",
        'bojack' : "Bojack Horseman",
        'cook' : "Cooking Tutorial",
    }
    f = plt.figure(figsize=(50,5))
    for i, video in enumerate(args.video):
        cur_dir = os.path.dirname(os.path.abspath(__file__))

        vmaf_path = f'{cur_dir}/videos/{video}/vmaf.json'
        tracks_path = f'{cur_dir}/videos/{video}/tracks'
        manifest_path = f'{tracks_path}/manifest.mpd'

        vmaf_json = json.loads(open(vmaf_path, 'r').read())
        qualities = [int(q) for q in vmaf_json.keys()]

        info = {q : [
            process_info(vmaf_json[str(q)][str(i + 1)], q, i + 1, tracks_path)
            for i in range(len(vmaf_json[str(q)]))
        ] for (i, q) in list(enumerate(qualities))}

        ax = f.add_subplot(int(f'1{len(args.video)}{i + 1}'))
        ks = sorted(list(info.keys()))

        ax.set_xlabel("segment")
        if i == 0:
            ax.set_ylabel("VMAF")

        for q, i in info.items():
            ax.plot([x['vmaf'] for x in i], label=q)
        ax.legend(loc=3)
        ax.title.set_text(text[video])

    plt.show()

if __name__ == "__main__":
    parser = ArgumentParser(description='Plot VMAF structure for a list of videos.') 
    parser.add_argument('video', nargs="*", type=str, help='Name of the video.')
    main(parser.parse_args())
