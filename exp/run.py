import shutil
import os

from argparse import ArgumentParser
from pathlib import Path

from components.monitor import Monitor 
from components.plots import LivePlot
from components.complete import OnComplete
from controller import Controller
from server import Server, multiple_sync


if __name__ == "__main__":
    parser = ArgumentParser(description='Run an experiment.')
    parser.add_argument('--port', type=int, default=8080, help='Port(default 8080).')
    parser.add_argument('--path', type=str, default='logs/default', help='Experiment folder path.')
    parser.add_argument('--only-server', dest='only_server', action='store_true', help='Use only as metrics server.')
    parser.add_argument('--delay', type=int,  help='Delay of the link.')
    parser.add_argument('--bandwidth', type=int, help='Bandwidth of the link.')
    parser.add_argument('-d','--dash', action='append', help='Add arguments to dash player.')
    args = parser.parse_args()
    path = Path(args.path)

    shutil.rmtree(path, ignore_errors=True)
    os.system(f"mkdir -p {path}")

    controller = Controller(
        bw = getattr(args, 'bw', None),
        delay = getattr(args, 'delay', None),
        dash = args.dash,
        only_server = args.only_server,
        port = args.port,
        path = path,
    )
    plots = {
        'qoe' : LivePlot(figure_name='qoe', y_label='qoe'),
        'rebuffer' : LivePlot(figure_name='rebuffer', y_label='rebuffer'),
        'switch' : LivePlot(figure_name='switch', y_label='switch'),
        'quality' : LivePlot(figure_name='quality', y_label='quality'),
    }
    (Server('experiment', args.port)
        .add_post('/init', controller.on_init())
        .add_post('/start', controller.on_start())
        .add_post('/metrics', Monitor(path))
        .add_post('/qoe', plots['qoe'])
        .add_post('/rebuffer', plots['rebuffer'])
        .add_post('/switch', plots['switch'])
        .add_post('/quality', plots['quality'])
        .add_post('/complete', multiple_sync(
            OnComplete(path, plots), 
            controller.on_complete(),
        )) 
        .add_post('/destroy', controller.on_destroy())
        .run())
