from pathlib import Path

from runner_genesis.backtest import Backtester
from runner_genesis.config import load_settings
from runner_genesis.demo import make_demo
from runner_genesis.ingestion.replay import ReplaySource
from runner_genesis.orchestrator import RunnerGenesisOmega


def test_demo_backtest_isolated_from_paper_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    p = make_demo(tmp_path / "demo.jsonl")

    settings = load_settings("config/default.yaml")
    settings.database_url = f"sqlite:///{tmp_path / 'paper.db'}"
    paper_engine = RunnerGenesisOmega(settings)

    # Deliberately contaminate PAPER persistence with an event/checkpoint first.
    first_event = next(ReplaySource(str(p)).events())
    paper_engine.process(first_event)
    assert paper_engine.repository is not None
    assert paper_engine.repository.has_event(first_event.event_id)

    backtester = Backtester(paper_engine)
    assert backtester.engine is not paper_engine
    assert backtester.engine.settings.mode == "BACKTEST"
    assert backtester.engine.repository is None

    metrics = backtester.run(str(p))
    assert metrics.events > 20
    assert metrics.decisions == metrics.events
    assert metrics.ending_equity_eur > 0
