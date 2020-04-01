from argparse import ArgumentParser, Namespace

import os
import json


def main(args: Namespace) -> None:
    cur_dir = os.path.dirname(os.path.abspath(__file__))

    vmaf_path = f'{cur_dir}/videos/{args.video}/vmaf.json'
    tracks_path = f'{cur_dir}/videos/{args.video}/tracks'
    manifest_path = f'{tracks_path}/manifest.mpd'

    vmaf_json = json.loads(open(vmaf_path, 'r').read())
    qualities = [int(q) for q in vmaf_json.keys()]
    
    config = {
        "domain" : "www.example.org",
        "base_path" : "/../", # [TODO] make absolute path
        "player" : {
            "index" : "/index.html",
            "manifest" : "/manifest.mpd",
            "player" : "/dist/bundle.js"
        },
        "segments" : len(vmaf_json[str(qualities[0])]),
        "video_paths" : [
            {
                "resource" : "/video" + str(len(qualities) - 1 - i),
                "quality" : q,
                "path" : f"/video_{q}",
                "info" : [
                    vmaf_json[str(q)][str(i + 1)]
                    for i in range(len(vmaf_json[str(q)]))
                ],
            } for (i, q) in list(enumerate(qualities))
        ],
    }

    # save the video
    os.system(f'rm -rf {cur_dir}/../quic/sites/{args.video}')
    os.system(f'cp -r {cur_dir}/videos/{args.video}/tracks {cur_dir}/../quic/sites/{args.video}')
    os.system(f'rm -rf {cur_dir}/../quic/sites/{args.video}/tracks')

    # save the config
    with open(f'{cur_dir}/../quic/sites/{args.video}/config.json', 'w') as f:
        f.write(json.dumps(config))


if __name__ == "__main__":
    parser = ArgumentParser(description='Prepare JSON compatible with QUIC programme.') 
    parser.add_argument('video', type=str, help='Name of the video.')
    main(parser.parse_args())   
