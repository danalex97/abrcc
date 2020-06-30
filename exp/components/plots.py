import matplotlib.pyplot as plt
import matplotlib.animation as animation

import numpy as np
import time
import asyncio

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from typing import Optional, Dict, Tuple, List 
from timeit import default_timer as timer

from abr.video import get_approx_video_length, get_video_chunks
from server.server import do_nothing, Server, Component, JSONType
from server.data import Value


plt.style.use('ggplot')

HORIZONTAL = 3
VERTICAL = 2
RANGE_SIZE = 50


def make_canvases() -> Tuple[Figure, List[Axes]]:
    fig, axes = plt.subplots(VERTICAL, HORIZONTAL, sharex=False, sharey=False)

    plots = []
    for i in range(VERTICAL):
        for j in range(HORIZONTAL):
            plots.append(axes[i, j])
    
    fig.tight_layout()
    plt.show(block=False)
    window = plt.get_current_fig_manager().window

    plt.get_current_fig_manager().resize(
        window.winfo_screenwidth(),
        window.winfo_screenheight())
    
    return fig, plots[:]


class Dataset:
    def __init__(self, axes: Axes, name: str, range_size: int) -> None:
        self.axes = axes
        self.name = name 

        self.x = list(range(0, range_size + 1))
        self.y = [0] * (range_size + 1)
        self.w = [0] * (range_size + 1)
       
        self.data, = self.axes.plot(self.x, self.y, label=name)

    def update(self, x: int, y: float, w: float) -> None: 
        while len(self.x) < x - 1:
            self.x.append(len(self.x))
            self.y.append(y)
            self.w.append(w)
        if self.w[x - 1] <= w:
            self.x[x - 1] = x
            self.y[x - 1] = y
            self.w[x - 1] = w

    def update_before(self, x: int, y: float, w: float) -> None:
        old_value = 0
        if x < len(self.x):
            old_value = self.y[x]
        self.update(x + 1, y, w)
        while len(self.x) < x:
            self.x.append(len(self.x))
            self.y.append(y)
            self.w.append(w)
        if self.w[x] <= w:
            self.x[x] = x
            self.y[x] = y
            self.w[x] = w
        pl = x - 1
        while pl >= 0 and (self.y[pl] == 0 or (self.w[pl] <= w and self.y[pl] == old_value)):
            self.y[pl] = y
            self.w[pl] = w
            pl -= 1

    def draw(self) -> None:
        self.data.set_xdata(self.x)
        self.data.set_ydata(self.y)


class LivePlot(Component):
    FIGURE: Optional[Figure] = None
    AXES: List[Axes] = []

    @classmethod
    def get_canvas(cls) -> Axes:
        if cls.FIGURE == None:
            cls.FIGURE, cls.AXES = make_canvases()
        axes = cls.AXES[-1]
        cls.AXES.pop()
        return axes 

    def __init__(self, 
        figure_name: str="default", 
        y_label: str="y_label", 
        range_size: int=RANGE_SIZE,
    ) -> None:
        super().__init__()
        
        self.axes: Axes = self.get_canvas()
        self.figure: Figure = self.FIGURE
        
        self.range_size: int = range_size
        self.datasets: Dict[str, Dataset] = {}

        self.axes.set_xlabel("time(segment)")
        self.axes.set_ylabel(y_label)
        self.axes.set_title(figure_name)
        self.axes.grid()

        minor_ticks = np.arange(0, 50, 1)
        self.axes.set_xticks(minor_ticks, minor=True)

        self.axes.grid(which='minor', alpha=0.2)
        self.axes.grid(which='major', alpha=0.5)

        self.first_call = True
        self.last_referesh = timer()

    async def update(self, name: str, x: int, y: float, w: float) -> None:
        if name not in self.datasets:
            self.datasets[name] = Dataset(
                axes=self.axes,
                name=name,
                range_size=self.range_size,
            )
            self.axes.legend(loc="upper left")

        dataset = self.datasets[name]
        dataset.update(x, y, w)

        if self.first_call:
            asyncio.ensure_future(
                self.draw(auto=True, limit_y=True)
            )
            self.first_call = False

    async def draw(self, auto: bool = False, limit_y: bool = False) -> None:
        for dataset in self.datasets.values():
            dataset.draw()
        ys = sum([d.y for d in self.datasets.values()], [])
        if limit_y:
            self.axes.set_ylim([min(ys) * 1.15, max(ys) * 1.15])
        
        self.figure.canvas.draw()
        self.last_referesh = timer()

        if auto:
            await asyncio.sleep(1)
            asyncio.ensure_future(
                self.draw(auto=True, limit_y=limit_y)
            )

    async def process(self, json: JSONType) -> JSONType:
        name  = json['name']
        value = Value.from_json(json['value'])
        watermark = json.get('timestamp', 0)

        await self.update(name, value.timestamp, value.value, watermark)
        if timer() - self.last_referesh > 3:
            await self.draw(auto=False, limit_y=True)

        return 'OK'


class BandwidthPlot(LivePlot):
    def __init__(self, 
        figure_name: str="default", 
        y_label: str="y_label",
        range_size: int=300, # seconds
        trace: Optional[str] =  None,
        bandwidth: Optional[int] = None,
    ) -> None:
        self.limit_y = (trace or bandwidth) is None
        if trace != None:   
            Component.__init__(self)
            to_timestamp = lambda x: tuple(map(float, x))
            with open(trace, 'r') as f:
                content = f.read()
                content.replace('\t', ' ')
                trace = [
                    to_timestamp(line.split())
                    for line in content.split('\n')
                    if line != ''
                ]
                xs = [t[0] for t in trace]
                ys = [t[1] for t in trace]
                
                range_size = int(max(xs)) + 1
                super().__init__(figure_name, y_label, range_size)

                self.axes.plot(xs, ys, linestyle='--', color='k', linewidth=1)                 
                self.axes.set_ylim([min(ys) * 1.15, max(ys) * 1.15])
        else:
            super().__init__(figure_name, y_label, range_size)
            if bandwidth:
                self.axes.set_ylim([0, bandwidth * 1.15])

        self.axes.set_xlabel("time(s)")
        
        self.axes.grid()
        self.axes.grid(which='minor', alpha=0.2)
        self.axes.grid(which='major', alpha=0.5)
        self.axes.grid()

    async def update(self, name: str, x: int, y: float, w: float) -> None:
        # [TODO] remove duplication
        if name not in self.datasets:
            self.datasets[name] = Dataset(
                axes=self.axes,
                name=name,
                range_size=self.range_size,
            )
            self.axes.legend(loc="upper left")

        dataset = self.datasets[name]
        dataset.update_before(x, y, w)

        if self.first_call:
            asyncio.ensure_future(
                self.draw(auto=True, limit_y=self.limit_y)
            )
            self.first_call = False
    
    async def process(self, json: JSONType) -> JSONType:
        name  = json['name']
        value = Value.from_json(json['value'])
        watermark = json.get('timestamp', 0)

        await self.update(name, value.timestamp, value.value, watermark)
        if timer() - self.last_referesh > 3:
            await self.draw(auto=False, limit_y=self.limit_y)

        return 'OK'


def attach_plot_components(
    video: str, 
    server: Server,
    trace: Optional[str] = None,
    bandwidth: Optional[int] = None,
    no_plot: bool = False, 
) -> Dict[str, LivePlot]:
    segments = get_video_chunks(video) + 1
    max_playback = int(1.25 * get_approx_video_length(video))

    if no_plot:
        (server
            .add_post('/raw_qoe', do_nothing) 
            .add_post('/rebuffer', do_nothing)
            .add_post('/quality', do_nothing)
            .add_post('/vmaf', do_nothing)
            .add_post('/vmaf_qoe', do_nothing)
            .add_post('/bw', do_nothing))
        return {}
    plots = {
        'raw_qoe' : LivePlot(figure_name='qoe', y_label='raw qoe', range_size=segments),
        'rebuffer' : LivePlot(figure_name='rebuffer', y_label='rebuffer', range_size=segments),
        'quality' : LivePlot(figure_name='quality', y_label='quality', range_size=segments),
        'vmaf' : LivePlot(figure_name='vmaf', y_label='vmaf', range_size=segments),
        'vmaf_qoe' : LivePlot(figure_name='vmaf_qoe', y_label='vmaf qoe', range_size=segments),
        'bw' : BandwidthPlot(
            figure_name='bw', 
            y_label='bw estimation(mbps)',
            trace=trace,
            bandwidth=bandwidth,
            range_size=max_playback,
        ),
    }
    (server
        .add_post('/raw_qoe', plots['raw_qoe'])
        .add_post('/rebuffer', plots['rebuffer'])
        .add_post('/quality', plots['quality'])
        .add_post('/vmaf', plots['vmaf'])
        .add_post('/vmaf_qoe', plots['vmaf_qoe'])
        .add_post('/bw', plots['bw']))
    return plots
