import os.path
import json
import xml.etree.ElementTree as et

from argparse import ArgumentParser, Namespace
from subprocess import check_output
from typing import Dict
from xml.etree.ElementTree import tostring

from vmaf.config import VmafConfig


def run_cmd(command: str, verbose: bool = False) -> str:
    if verbose:
        print(f'> {command}')
    return check_output(command, shell=True).decode('utf-8')


def get_tracks(url: str) -> Dict[int, int]:
    raw_info = run_cmd(f'youtube-dl -F {url}')
    print(raw_info)

    out = {}
    for line in raw_info.split('\n')[3:-1]:
        info = [s for s in line.split('  ') if s != '']
        print(line)

        track_id = int(info[0])
        track_format = info[1]

        rest = (' '.join(info[2:])).split(' ')
        rest = [r for r in rest if r != '']
        is_video = 'video' in ''.join(rest)
        is_avc = 'avc' in ''.join(rest)
        if not is_video or not is_avc:
            continue

        rate = int(rest[2][:-1])
        if track_format == 'mp4':
            out[rate] = track_id

    max_rate = 2500

    to_delete = []
    for rate in out.keys():
        if rate > max_rate:
            to_delete.append(rate)
    for rate in to_delete:
        del out[rate]

    return out


def convert_to_yuv(raw_video: str, width: int, height: int, rate: int) -> None:
    where = f"videos/{raw_video}/yuv/video_{rate}.yuv"
    run_cmd(f"rm *.yuv || true")
    run_cmd(f"fm {where} || true")

    video = f"videos/{raw_video}/tmp/video_{rate}.mp4"
    scale = f"-vf scale={width}:{height}"
    fmt   = f"-pix_fmt yuv420p"
    run_cmd(f"ffmpeg -y -i {video} {fmt} -vsync 0 {scale} output_{rate}.yuv")

    run_cmd(f"mv output_{rate}.yuv {where}")


def get_attr(raw_xml: str, attr: str) -> str:
    return raw_xml.split(attr)[1].split('"')[1]


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
    segment_info = {}
    ctr = 0
    for rate, track_id in tracks.items():
        run_cmd(f'mkdir -p videos/{args.video}/tracks')
        mp4_video = f'videos/{args.video}/tmp/video_{rate}.mp4'

        segment_dir = f'videos/{args.video}/tracks/video_{rate}'
        run_cmd(f'rm -rf {segment_dir}')
        run_cmd(f'mkdir -p {segment_dir}')

        # Intermediate video -- H264 format
        inter1 = f'videos/{args.video}/tmp/intermediate.264'
        run_cmd(f'x264 --output {inter1} --fps 24 --preset slow' +
                f' --bitrate {rate} --vbv-maxrate {2*rate} --vbv-bufsize {4*rate}' +
                f' --min-keyint {args.segment*24} --keyint {args.segment*24}' +
                f' --scenecut 0 --no-scenecut --pass 1 {mp4_video}')

        # Intermediate video -- mp4 format
        inter2 = f'videos/{args.video}/tmp/intermediate.mp4'
        run_cmd(f'rm -f {inter2}')
        run_cmd(f'MP4Box -add {inter1} -fps 24 {inter2}')

        # To segemnts
        #run_cmd(f'MP4Box -dash {args.segment*1000} -frag {args.segment*1000} -rap -segment-name "" {inter2}', verbose=True)
        #run_cmd(f'MP4Box -dash {args.segment*1000} -segment-name "" {inter2}', verbose=True)
        run_cmd(f'MP4Box -dash {args.segment*1000} -dash-profile live -rap -segment-name "" {inter2}', verbose=True)
        run_cmd(f'mv intermediate_dash.mpd {segment_dir}')
        run_cmd(f'mv *.m4s {segment_dir}')
        run_cmd(f'mv init.mp4 {segment_dir}')

        segments = int(run_cmd(f'ls {segment_dir} | grep "m4s" | wc -l'))
        segment_info[rate] = {}
        for segment in range(1, segments + 1):
            segment_info_raw = run_cmd(f'MP4Box -std -diso {segment_dir}/{segment}.m4s 2>&1 | grep "SegmentIndexBox"')
            timescale = int(get_attr(segment_info_raw, 'timescale'))
            earliest_time = int(get_attr(segment_info_raw, 'earliest_presentation_time'))

            # compute segment start times
            segment_info[rate][segment] = {
                'start_time' : earliest_time / timescale,
            }

    # Create common manifest
    base = None
    info = {}
    for rate, track_id in tracks.items():
        segment_dir = f'videos/{args.video}/tracks/video_{rate}'
        manifest = f'{segment_dir}/intermediate_dash.mpd'

        # Remove unused manifest files
        content = None
        with open(manifest, 'r') as f:
            content = f.read()
            content = '\n'.join([l for l in content.split('\n')
                if "Initialization" not in l])
        os.system(f'rm {manifest}')
        with open(manifest, 'w') as f:
            f.write(content)

        tree = et.parse(manifest)
        tree = tree.getroot()

        root = tree[1][0]
        representation = None
        for child in root:
            if 'Representation' in child.tag:
                representation = child

        print(representation)
        pl = sorted(list(tracks.keys())).index(rate)
        representation.set('id', f"video{pl}")

        # Save video representation information
        info[rate] = {
            'width' : int(representation.get('width')),
            'height' : int(representation.get('height')),
        }
        if base is None:
            base = tree
            segment_template = tree[1][0][0]
            segment_template.set('initialization', '$RepresentationID$/init.mp4')
            segment_template.set('media', '$RepresentationID$/$Number$.m4s')
        else:
            base[1][0].append(representation)

    # Generate manifest
    manifest = f'videos/{args.video}/tracks/manifest.mpd'
    print(f'> Creating manifest {manifest}')

    run_cmd(f'rm {manifest} || true')
    with open(manifest, 'w') as f:
        manifest_content = tostring(base).decode('UTF-8')
        print(manifest_content)
        f.write(manifest_content)

    if not args.vmaf:
        return

    # Generate JSON vmaf information
    if not os.path.isfile(f'videos/{args.video}/vmaf.json'):
        # Convert MP4 to .yuv, then compute the vmaf of segments
        biggest_rate = max(tracks.keys())
        width = info[biggest_rate]['width']
        height = info[biggest_rate]['height']
        run_cmd(f'mkdir -p videos/{args.video}/yuv')
        convert_to_yuv(args.video, width, height, biggest_rate)

        run_cmd(f'mkdir -p videos/{args.video}/vmaf')
        for rate, track_id in tracks.items():
            if os.path.isfile(f"videos/{args.video}/vmaf/video_{rate}.json"):
                continue

            # convert video
            if rate != biggest_rate:
                convert_to_yuv(args.video, width, height, rate)

            video = f"videos/{args.video}/yuv/video_{rate}.yuv"
            video_ref = f"videos/{args.video}/yuv/video_{biggest_rate}.yuv"
            segments = max(segment_info[rate].keys())
            for segment in range(1, segments + 1):
                # cut each individual segment
                ss = segment_info[rate][segment]['start_time']
                t  = None
                if segment < segments:
                    t = segment_info[rate][segment + 1]['start_time'] - ss
                else:
                    t = (segment_info[rate][segment]['start_time'] -
                        segment_info[rate][segment - 1]['start_time'])

                cmd_ss = f"-ss {ss}"
                cmd_t = f"-t {t}"
                sizes = f"-s:v {width}x{height}"
                fmt = "-pix_fmt yuv420p"
                run_cmd(f"ffmpeg {sizes} -r 10 -i {video} {cmd_ss} {cmd_t} {fmt} cut1.yuv", verbose=True)
                run_cmd(f"ffmpeg {sizes} -r 10 -i {video_ref} {cmd_ss} {cmd_t} {fmt} cut2.yuv", verbose=True)

                command = f"vmaf/run_vmaf yuv420p {width} {height} cut2.yuv cut1.yuv --out-fmt json"
                raw_vmaf_data = run_cmd(command)

                vmaf_data = json.loads(raw_vmaf_data)
                segment_info[rate][segment]["vmaf"] = float(vmaf_data["aggregate"]["VMAF_score"])
                run_cmd(f"rm *.yuv")

            # remove video
            if rate != biggest_rate:
                where = f"videos/{args.video}/yuv/video_{rate}.yuv"
                run_cmd(f"rm {where}")
        run_cmd(f"rm -rf videos/{args.video}/yuv")
        run_cmd(f"rm -rf videos/{args.video}/vmaf")

        # save segment data
        with open(f'videos/{args.video}/vmaf.json', 'w') as f:
            out = json.dumps(segment_info)
            f.write(out)

    # print vmafs
    with open(f'videos/{args.video}/vmaf.json', 'r') as f:
        son = json.loads(f.read())
        for rate, sson in son.items():
            vmafs = []
            for seg, info in sson.items():
                vmafs.append(info['vmaf'])
            print(vmafs)

if __name__ == "__main__":
    parser = ArgumentParser(description='Download and make a DASH.js compliant video.')
    parser.add_argument('url', type=str, help='Video url.')
    parser.add_argument('video', type=str, help='Name of the video.')
    parser.add_argument('-s', '--segment-size', dest='segment', type=int, default=5000, help='Segment size in ms.')
    parser.add_argument('-vmaf', action='store_true', dest='vmaf', help='Generate VMAF configuration.')
    run(parser.parse_args())
