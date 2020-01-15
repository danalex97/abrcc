import json

from pathlib import Path
from typing import List, Dict

from server.server import Component, JSONType
from .plots import LivePlot


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
        if len(self.plots) > 0:
            ref_plot = list(self.plots.values())[1]
            with open(self.plots_path, 'a') as f:
                xs = ref_plot.x
                for x in xs:
                    out = {'x' : x}
                    for name, plot in self.plots.items():
                        out[name] = plot.y[x]
                    f.write(json.dumps(out))
                    f.write('\n')
            ref_plot.figure.savefig(self.draw_path)
        
    async def process(self, json: JSONType) -> JSONType:
        if 'logs' in json:
            browser_logs = json['logs']
            await self.process_logs(browser_logs),
        await self.export_plots()
        return 'OK'
