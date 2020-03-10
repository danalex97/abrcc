import os

from argparse import ArgumentParser, Namespace
from threading import Thread


def generate_template(track: str) -> str:
    tmp = """
        <!DOCTYPE html>
        <html>

        <script src="https://cdn.dashjs.org/latest/dash.all.min.js"></script>
        <body>
            <div>
                <video data-dashjs-player autoplay src="{track}" controls></video>
            </div>
        </body>

        </html>
    """
    return tmp.format(track=track)


def server() -> None:
    os.system('python3 -m http.server 8000')


def run(args: Namespace) -> None:
    template = generate_template(args.manifest)
    
    os.system('mkdir tmp')
    tmp = 'tmp/template.html'
    os.system(f'rm {tmp}')
    with open(tmp, 'w') as f:
        f.write(template)

    Thread(target=server).start()
    os.system(f'firefox localhost:8000/{tmp}')
    

if __name__ == "__main__":
    parser = ArgumentParser(description='Test a DASH.js video from a manifest.') 
    parser.add_argument('-m', '--manifest', default='../videos/bojack/tracks/manifest.mpd', type=str, help='Manifest path.')
    run(parser.parse_args()) 
