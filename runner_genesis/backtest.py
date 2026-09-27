from __future__ import annotations
from dataclasses import dataclass
from .orchestrator import RunnerGenesisOmega
from .ingestion.replay import ReplaySource

@dataclass
class BacktestMetrics:
    events:int; decisions:int; fills:int; failed_fills:int; ending_equity_eur:float; net_pnl_eur:float; roi:float; max_drawdown_pct:float

class Backtester:
    def __init__(self,engine:RunnerGenesisOmega): self.engine=engine
    def run(self,path:str)->BacktestMetrics:
        events=0; max_dd=0.0
        for e in ReplaySource(path).events():
            events+=1; self.engine.process(e)
            a=self.engine.portfolio.account
            dd=(a.peak_equity_eur-a.equity_eur)/max(a.peak_equity_eur,1e-9); max_dd=max(max_dd,dd)
        a=self.engine.portfolio.account
        fills=self.engine.portfolio.fills
        pnl=a.equity_eur-a.starting_cash_eur
        return BacktestMetrics(events,len(self.engine.decisions),len(fills),sum(f.failed for f in fills),a.equity_eur,pnl,pnl/max(a.starting_cash_eur,1e-9),max_dd)
