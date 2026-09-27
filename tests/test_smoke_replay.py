from pathlib import Path
from runner_genesis.config import load_settings
from runner_genesis.orchestrator import RunnerGenesisOmega
from runner_genesis.demo import make_demo
from runner_genesis.backtest import Backtester

def test_demo_backtest(tmp_path,monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    p=make_demo(tmp_path/'demo.jsonl')
    eng=RunnerGenesisOmega(load_settings('config/default.yaml'))
    m=Backtester(eng).run(str(p))
    assert m.events>20
    assert m.decisions==m.events
    assert m.ending_equity_eur>0
