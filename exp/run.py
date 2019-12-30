from argparse import ArgumentParser

from monitor import Monitor 
from plots import LivePlot
from server import Server, multiple


if __name__ == "__main__":
    parser = ArgumentParser(description='')
    parser.add_argument('--port', type=int, default=8080, help='Port(default 8080).')
    parser.add_argument('--path', type=str, default='logs/log.txt', help='Path of the monitor.')
    args = parser.parse_args()
    
    monitor = Monitor(args.path)
    (Server('experiment', args.port)
        .add_post('/metrics', monitor)
        .add_post('/qoe', LivePlot(figure_name='qoe', y_label='qoe'))
        .add_post('/rebuffer', LivePlot(figure_name='rebuffer', y_label='rebuffer'))
        .add_post('/switch', LivePlot(figure_name='switch', y_label='switch'))
        .add_post('/quality', LivePlot(figure_name='quality', y_label='quality'))
        .run())
