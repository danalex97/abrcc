import shutil
import os

from argparse import ArgumentParser, Namespace
from pathlib import Path

from components.monitor import Monitor 
from components.plots import LivePlot
from components.complete import OnComplete
from controller import Controller
from server.server import Server, multiple_sync
from scripts.network import Network


def run(args: Namespace) -> None:
    path = Path(args.path)
    name = args.name

    if not args.leader_port:  
        shutil.rmtree(path, ignore_errors=True)
        os.system(f"mkdir -p {path}")

    controller = Controller(
        name = name,
        site = args.site,
        network = Network(
            bandwidth=getattr(args, 'bandwidth', None),
            delay=getattr(args, 'delay', None),
            trace_path=getattr(args, 'trace', None),
            ports=[args.quic_port],
        ),
        dash = args.dash,
        quic_port = args.quic_port,
        only_server = args.only_server,
        port = args.port,
        path = path,
        leader_port = args.leader_port,
    )
    
    server = Server('experiment', args.port)
        
    request_port = args.leader_port if args.leader_port else args.port 
    (server
        .add_post('/init', controller.on_init())
        .add_post('/start', controller.on_start())
        .add_post('/metrics', Monitor(
            path = path, 
            name = name,
            plot = args.plot or (args.leader_port != None), 
            request_port = request_port,
            port = args.port,
        ))
        .add_post('/destroy', controller.on_destroy()))

    plots = {}
    if args.plot:
        plots = {
            'qoe' : LivePlot(figure_name='qoe', y_label='qoe'),
            'rebuffer' : LivePlot(figure_name='rebuffer', y_label='rebuffer'),
            'switch' : LivePlot(figure_name='switch', y_label='switch'),
            'quality' : LivePlot(figure_name='quality', y_label='quality'),
        }
        (server
            .add_post('/qoe', plots['qoe'])
            .add_post('/rebuffer', plots['rebuffer'])
            .add_post('/switch', plots['switch'])
            .add_post('/quality', plots['quality']))

    server.add_post('/complete', multiple_sync(
        OnComplete(path, name, plots), 
        controller.on_complete(),
    )) 
    server.run()


if __name__ == "__main__":
    parser = ArgumentParser(description='Run a single video instance.')
    parser.add_argument('--name', type=str, default='default', help='Instance name. Must be specified when running with a leader.')
    parser.add_argument('--site', type=str, default='www.example.org', help='Site name of instance served in chrome')
    parser.add_argument('--quic-port', type=int, default=6000, help="Port for QUIC server.")
    parser.add_argument('--port', type=int, default=8080, help='Port(default 8080).')
    parser.add_argument('--path', type=str, default='logs/default', help='Experiment folder path.')
    parser.add_argument('--only-server', dest='only_server', action='store_true', help='Use only as metrics server.')
    parser.add_argument('-l', '--delay', type=float,  help='Delay of the link.')
    parser.add_argument('-b', '--bandwidth', type=float, help='Bandwidth of the link.')
    parser.add_argument('-t', '--trace', type=str, help='Trace of bandwidth.')
    parser.add_argument('-d','--dash', action='append', help='Add arguments to dash player.')
    parser.add_argument('--plot', action='store_true', help='Enable plotting.')
    parser.add_argument('-lp', '--leader-port', dest='leader_port', type=int, required=False, help='Port of the leader.')
    run(parser.parse_args())   
