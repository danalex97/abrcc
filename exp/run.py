import shutil
import os

from argparse import ArgumentParser, Namespace
from pathlib import Path

from components.monitor import Monitor 
from components.plots import attach_plot_components
from components.complete import OnComplete
from controller import Controller
from server.server import Server, multiple_sync
from scripts.network import Network


ABR_ALGORITHMS = ['bola', 'bb', 'festive', 'rb', 'robustMpc', 'pensieve']
SERVER_ABR_ALGORITHMS = ['bb', 'random', 'worthed', 'target', 'target2']
CC_ALGORITHMS = ['bbr', 'pcc', 'reno', 'cubic', 'abbr', 'xbbr', 'target']
PYTHON_ABR_ALGORITHMS = ['robustMpc', 'pensieve']


def run(args: Namespace) -> None:
    path = Path(args.path)
    name = args.name

    if not args.leader_port:  
        shutil.rmtree(path, ignore_errors=True)
        os.system(f"mkdir -p {path}")

    if args.algo is not None:
        if args.dash is None:
            args.dash = []
        if args.algo in ABR_ALGORITHMS:
            args.dash.append(f'fe={args.algo}')
        

    server = Server('experiment', args.port)
 
    # Haandle Abr requests
    if args.algo in PYTHON_ABR_ALGORITHMS:
        if args.algo == 'robustMpc':
            from abr.robust_mpc import RobustMpc
            server.add_post('/decision', RobustMpc(args.video))
        elif args.algo == 'pensieve':
            from abr.pensieve import Pensieve
            server.add_post('/decision', Pensieve(args.video))

    # Add controller for launching the QUIC server and browser 
    controller = Controller(
        name = name,
        site = args.site,
        cc = args.cc,
        abr = args.server_algo,
        network = Network(
            bandwidth=getattr(args, 'bandwidth', None),
            delay=getattr(args, 'delay', None),
            trace_path=getattr(args, 'trace', None),
            burst=getattr(args, 'burst', None),
            ports=[args.quic_port],
        ),
        dash = args.dash,
        quic_port = args.quic_port,
        only_server = args.only_server,
        port = args.port,
        path = path,
        leader_port = args.leader_port,
        video = args.video,
    )
       
    # Handle controller communication and metrics
    request_port = args.leader_port if args.leader_port else args.port 
    (server
        .add_post('/init', controller.on_init())
        .add_post('/start', controller.on_start())
        .add_post('/metrics', Monitor(
            video = args.video,
            path = path, 
            name = name,
            plot = args.plot or (args.leader_port != None), 
            request_port = request_port,
            port = args.port,
        ))
        .add_post('/destroy', controller.on_destroy()))
    
    # Handle live plots
    plots = attach_plot_components(
        args.video,
        server,
        trace=getattr(args, 'trace', None),
        no_plot=not args.plot,
    )
    
    # Handle stream completion in the Browser
    server.add_post('/complete', multiple_sync(
        OnComplete(path, name, plots, args.video), 
        controller.on_complete(),
    )) 
    server.run()


if __name__ == "__main__":
    parser = ArgumentParser(description='Run a single video instance.')
    parser.add_argument('--name', type=str, default='default', help='Instance name. Must be specified when running with a leader.')
    parser.add_argument('--video', type=str, default='bojack', help='Video name.')
    parser.add_argument('--site', type=str, default='www.example.org', help='Site name of instance served in chrome')
    parser.add_argument('--quic-port', type=int, default=6010, help="Port for QUIC server.")
    parser.add_argument('--port', type=int, default=8080, help='Port(default 8080).')
    parser.add_argument('--path', type=str, default='logs/default', help='Experiment folder path.')
    parser.add_argument('--only-server', dest='only_server', action='store_true', help='Use only as metrics server.')
    parser.add_argument('-l', '--delay', type=float,  help='Delay of the link.')
    parser.add_argument('-b', '--bandwidth', type=float, help='Bandwidth of the link.')
    parser.add_argument('--burst', type=int, help='Burst for tc.')
    parser.add_argument('-t', '--trace', type=str, help='Trace of bandwidth.')
    parser.add_argument('-d','--dash', action='append', help='Add arguments to dash player.')
    parser.add_argument('--algo', choices=ABR_ALGORITHMS, help='Choose abr algorithm.') 
    parser.add_argument('--server-algo', choices=SERVER_ABR_ALGORITHMS, help='Choose server abr algorithm.')
    parser.add_argument('--cc', choices=CC_ALGORITHMS, default='bbr', help='Choose cc algorithm.') 
    parser.add_argument('--plot', action='store_true', help='Enable plotting.')
    parser.add_argument('-lp', '--leader-port', dest='leader_port', type=int, required=False, help='Port of the leader.')
    run(parser.parse_args())   
