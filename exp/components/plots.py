import matplotlib.pyplot as plt
import matplotlib.animation as animation

import numpy as np
import time
import asyncio

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from typing import Optional, Dict, Tuple, List 
from timeit import default_timer as timer

from server.server import Component, JSONType
from server.data import Value


plt.style.use('ggplot')

HORIZONTAL = 2
VERTICAL = 2
RANGE_SIZE = 50


def make_canvases() -> Tuple[Figure, List[Axes]]:
    fig, axes = plt.subplots(HORIZONTAL, VERTICAL, sharex=False, sharey=False)

    plots = []
    for i in range(HORIZONTAL):
        for j in range(VERTICAL):
            plots.append(axes[i, j])
    
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

        self.x = list(range(0, range_size))
        self.y = [0] * range_size
       
        self.data, = self.axes.plot(self.x, self.y, label=name)

    def update(self, x: int, y: float) -> None: 
        while len(self.x) < x - 1:
            self.x.append(len(self.x))
            self.y.append(0)
        self.x[x - 1] = x
        self.y[x - 1] = y
    
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
        figure_name="default", 
        y_label="y_label", 
        range_size=RANGE_SIZE, 
    ) -> None:
        self.axes: Axes = self.get_canvas()
        self.figure: Figure = self.FIGURE
        
        self.range_size: int = RANGE_SIZE
        self.datasets: Dict[str, Dataset] = {}

        self.axes.set_xlabel("time(segment)")
        self.axes.set_ylabel(y_label)
        self.axes.set_title(figure_name)

        self.first_call = True
        self.last_referesh = timer()

    async def update(self, name: str, x: int, y: float) -> None:
        if name not in self.datasets:
            self.datasets[name] = Dataset(
                axes=self.axes,
                name=name,
                range_size=self.range_size,
            )
            self.axes.legend(loc="upper left")

        dataset = self.datasets[name]
        dataset.update(x, y)

        if self.first_call:
            asyncio.ensure_future(
                self.draw(auto=True)
            )
            self.first_call = False

    async def draw(self, auto: bool = False) -> None:
        for dataset in self.datasets.values():
            dataset.draw()
        ys = sum([d.y for d in self.datasets.values()], [])
        self.axes.set_ylim([min(ys) * 1.15, max(ys) * 1.15])
        
        self.figure.canvas.draw()
        self.last_referesh = timer()

        if auto:
            await asyncio.sleep(1)
            asyncio.ensure_future(
                self.draw(auto=True)
            )

    async def process(self, json: JSONType) -> JSONType:
        name  = json['name']
        value = Value.from_json(json['value'])
        
        await self.update(name, value.timestamp, value.value)
        if timer() - self.last_referesh > 3:
            await self.draw(auto=False)

        return 'OK'
