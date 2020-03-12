import os.path
import xml.etree.ElementTree as et

from argparse import ArgumentParser, Namespace
from subprocess import check_output
from typing import Dict
from xml.etree.ElementTree import tostring


def run_cmd(command: str, verbose: bool = False) -> str:
    if verbose:
        print(f'> {command}')
    return check_output(command, shell=True).decode('utf-8')  
    

def get_tracks(url: str) -> Dict[int, int]:
    raw_info = run_cmd(f'youtube-dl -F {url}')
    out = {}
    for line in raw_info.split('\n')[3:-1]:
        info = [s for s in line.split('  ') if s != '']
        
        track_id = int(info[0])
        track_format = info[1]
        
        rest = (' '.join(info[2:])).split(' ')
        rest = [r for r in rest if r != '']
        is_video = 'video' in ''.join(rest)
        is_avc = 'avc' in ''.join(rest)
        if not is_video and not is_avc:
            continue
        
        rate = int(rest[2][:-1])
        if track_format == 'mp4':
            out[rate] = track_id
    return out


def run(args: Namespace) -> None:
    tracks = get_tracks(args.url)
    run_cmd(f'mkdir -p videos')
    run_cmd(f'mkdir -p videos/{args.video}')
    
    # Download all tracks
    for rate, track_id in tracks.items():
        run_cmd(f'mkdir -p videos/{args.video}/tmp')
        fmt = f'videos/{args.video}/tmp/video_{rate}.mp4'

        print(f'> Downloading {fmt}')
        if not os.path.isfile(fmt):
            print(run_cmd(f'youtube-dl -f {track_id} -o {fmt} {args.url}', verbose=True))

    # Convert tracks
    for rate, track_id in tracks.items():
        run_cmd(f'mkdir -p videos/{args.video}/tracks')
        mp4_video = f'videos/{args.video}/tmp/video_{rate}.mp4'
        
        segment_dir = f'videos/{args.video}/tracks/video_{rate}'
        run_cmd(f'rm -rf {segment_dir}')
        run_cmd(f'mkdir -p {segment_dir}')
         
        run_cmd(f'MP4Box -dash {args.segment} -dash-profile live -segment-name out {mp4_video}', verbose=True)
        run_cmd(f'mv video_{rate}_dash.mpd {segment_dir}')
        run_cmd(f'mv out* {segment_dir}')

    # Create common manifest
    base = None
    for rate, track_id in tracks.items():
        segment_dir = f'videos/{args.video}/tracks/video_{rate}'
        manifest = f'{segment_dir}/video_{rate}_dash.mpd'
        
        tree = et.parse(manifest)
        tree = tree.getroot()
        
        representation = tree[1][0][1]
        representation.set('id', f"video_{rate}")

        if base is None:
            base = tree
            segment_template = tree[1][0][0]
            segment_template.set('initialization', '$RepresentationID$/outinit.mp4')
            segment_template.set('media', '$RepresentationID$/out$Number$.m4s')
        else:
            base[1][0].append(representation)

    manifest = f'videos/{args.video}/tracks/manifest.mpd'
    print(f'> Creating manifest {manifest}')
    
    run_cmd(f'rm {manifest} || true')
    with open(manifest, 'w') as f:
        manifest_content = tostring(base).decode('UTF-8')
        print(manifest_content)
        f.write(manifest_content)
    
if __name__ == "__main__":
    parser = ArgumentParser(description='Download and make a DASH.js complient video.') 
    parser.add_argument('url', type=str, help='Video url.')
    parser.add_argument('video', type=str, help='Name of the video.')
    parser.add_argument('-s', '--segment-size', dest='segment', type=int, default=5000, help='Segment size in ms.')
    run(parser.parse_args())   
