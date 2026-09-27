from datetime import datetime, timezone, timedelta
from pathlib import Path
from runner_genesis.config import load_settings
from runner_genesis.orchestrator import RunnerGenesisOmega, PendingPaperOrder
from runner_genesis.ai_trader import TradeProposal, Action
from runner_genesis.domain.events import MarketEvent, EventType


def test_entry_executes_only_at_or_after_configured_delay(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    settings = load_settings('config/default.yaml')
    settings.features['database_persistence']={'enabled':False}
    eng = RunnerGenesisOmega(settings)
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    token = eng.store.apply(MarketEvent(event_id='p0', timestamp=t0, token_mint='M', event_type=EventType.PRICE, price_usd=1.0, market_cap_usd=100_000, liquidity_usd=100_000))
    prop = TradeProposal(Action.ENTER, 'M', amount_eur=10)
    due = t0 + timedelta(seconds=settings.execution.execution_delay_seconds)
    eng.pending_orders['M'] = PendingPaperOrder(prop, t0, due, {})
    fill, reasons = eng._execute_due_pending('M', due-timedelta(seconds=1), token, {'entry_validity':'VALID','sellability_score':1.0,'manipulation_risk':0.0})
    assert fill is None and 'M' in eng.pending_orders
    fill, reasons = eng._execute_due_pending('M', due, token, {'entry_validity':'VALID','sellability_score':1.0,'manipulation_risk':0.0})
    assert fill is not None
    assert 'M' not in eng.pending_orders
    assert fill.timestamp >= due
