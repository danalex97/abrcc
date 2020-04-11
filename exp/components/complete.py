import json

from pathlib import Path
from typing import List, Dict

from server.server import Component, JSONType
from .plots import LivePlot, BandwidthPlot


class OnComplete(Component):
    def __init__(self, path: Path, name: str, plots: Dict[str, LivePlot]) -> None:
        self.browser_path= path / f'{name}_browser.log'
        self.plots_path = path / f'{name}_plots.log'
        self.draw_path = path / f'{name}_plots.png'

        self.plots = plots 
    
    async def process_logs(self, log: List[str]) -> None:
        with open(self.browser_path, 'a') as f:
            for line in log:
                f.write(line)
                f.write('\n')
  
    async def export_plots(self) -> None: 
        try:
            # [TODO] Fix plot exports
            for name, plot in self.plots.items():
                ref_dataset = (list(plot.datasets.values())[0]
                    if len(plot.datasets) > 0 else None)
                if not ref_dataset:
                    continue
                xs = ref_dataset.x

                with open(self.plots_path, 'a') as f:
                    for x in xs:
                        out = {'x' : x} 
                        out[name] = {}
                        for ds_name, dataset in plot.datasets.items():
                            out[name][ds_name] = dataset.y[x]
                        f.write(json.dumps(out))
                    f.write('\n')
        except:
            pass
        if len(self.plots) > 0:
            for plot in self.plots.values():
                await plot.draw()
            ref_plot = list(self.plots.values())[0]
            ref_plot.figure.savefig(self.draw_path)

    async def process(self, json: JSONType) -> JSONType:
        if 'logs' in json:
            browser_logs = json['logs']
            await self.process_logs(browser_logs),
        await self.export_plots()
        return 'OK'
