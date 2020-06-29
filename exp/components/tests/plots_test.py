import asyncio
import aiounittest
import unittest

from components.plots import BandwidthPlot
from components.plots import LivePlot


class HeadlessPlot(LivePlot):
    async def draw(self, auto: bool = False, limit_y: bool = False) -> None:
        pass


class HeadlessBwPlot(BandwidthPlot):
    async def draw(self, auto: bool = False, limit_y: bool = False) -> None:
        pass


class PlotTests(aiounittest.AsyncTestCase):
    async def test_plot_updates_dataset(self):
        print()
        plot = HeadlessPlot(
            figure_name='qoe', 
            y_label='quality', 
            range_size=5,
        )
        
        name = 'graph'
        for entry in [
            {'name': name, 'value': {'value': 1, 'timestamp': 1}},
            {'name': name, 'value': {'value': 2, 'timestamp': 2}},
            {'name': name, 'value': {'value': 2, 'timestamp': 3}},
            {'name': name, 'value': {'value': 2, 'timestamp': 4}},
            {'name': name, 'value': {'value': 1, 'timestamp': 5}},
            {'name': name, 'value': {'value': 1, 'timestamp': 4}},
            {'name': name, 'value': {'value': 5, 'timestamp': 3}},
        ]:
            await plot.process(entry)

        self.assertEquals(len(plot.datasets), 1)
        dataset = plot.datasets[name]

        self.assertEquals(dataset.x[:5], [1, 2, 3, 4, 5])
        self.assertEquals(dataset.y[:5], [1, 2, 5, 1, 1])

    async def test_plot_updates_dataset_async(self):
        print()
        plot = HeadlessPlot(
            figure_name='qoe', 
            y_label='quality', 
            range_size=5,
        )
        
        name = 'graph'
        for entry in [
            {'name': name, 'value': {'value': 1, 'timestamp': 1}, 'timestamp': 1},
            {'name': name, 'value': {'value': 2, 'timestamp': 2}, 'timestamp': 2},
            {'name': name, 'value': {'value': 2, 'timestamp': 3}, 'timestamp': 7},
            {'name': name, 'value': {'value': 2, 'timestamp': 4}, 'timestamp': 4},
            {'name': name, 'value': {'value': 1, 'timestamp': 5}, 'timestamp': 5},
            {'name': name, 'value': {'value': 1, 'timestamp': 4}, 'timestamp': 6},
            {'name': name, 'value': {'value': 5, 'timestamp': 3}, 'timestamp': 1},
        ]:
            await plot.process(entry)

        self.assertEquals(len(plot.datasets), 1)
        dataset = plot.datasets[name]

        self.assertEquals(dataset.x[:5], [1, 2, 3, 4, 5])
        self.assertEquals(dataset.y[:5], [1, 2, 2, 1, 1])

    async def test_bw_plot_updates_dataset(self):
        print()
        plot = HeadlessBwPlot(
            figure_name='qoe', 
            y_label='quality', 
            range_size=5,
        )
        
        name = 'graph'
        for entry in [
            {'name': name, 'value': {'value': 3, 'timestamp': 2}},
            {'name': name, 'value': {'value': 5, 'timestamp': 4}},
        ]:
            await plot.process(entry)

        self.assertEquals(len(plot.datasets), 1)
        dataset = plot.datasets[name]

        self.assertEquals(dataset.x[:5], [0, 1, 2, 3, 4])
        self.assertEquals(dataset.y[:5], [3, 3, 3, 5, 5])

    async def test_bw_plot_updates_dataset_async(self):
        print()
        plot = HeadlessBwPlot(
            figure_name='qoe', 
            y_label='quality', 
            range_size=5,
        )
        
        name = 'graph'
        for entry in [
            {'name': name, 'value': {'value': 3, 'timestamp': 2}, 'timestamp': 2},
            {'name': name, 'value': {'value': 2, 'timestamp': 4}, 'timestamp': 3},
            {'name': name, 'value': {'value': 5, 'timestamp': 4}, 'timestamp': 1},
        ]:
            await plot.process(entry)

        self.assertEquals(len(plot.datasets), 1)
        dataset = plot.datasets[name]

        self.assertEquals(dataset.x[:5], [0, 1, 2, 3, 4])
        self.assertEquals(dataset.y[:5], [3, 3, 3, 2, 2])

    async def test_bw_plot_updates_dataset_jumps(self):
        print()
        plot = HeadlessBwPlot(
            figure_name='qoe', 
            y_label='quality', 
            range_size=5,
        )
        
        name = 'graph'
        for entry in [
            {'name': name, 'value': {'value': 3, 'timestamp': 2}, 'timestamp': 2},
            {'name': name, 'value': {'value': 2, 'timestamp': 3}, 'timestamp': 3},
            {'name': name, 'value': {'value': 5, 'timestamp': 4}, 'timestamp': 1},
        ]:
            await plot.process(entry)

        self.assertEquals(len(plot.datasets), 1)
        dataset = plot.datasets[name]

        self.assertEquals(dataset.x[:5], [0, 1, 2, 3, 4])
        self.assertEquals(dataset.y[:5], [3, 3, 3, 2, 5])
