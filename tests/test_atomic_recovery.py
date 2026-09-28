from datetime import datetime, timedelta, timezone

import pytest

from runner_genesis.ai_trader import Action, TradeProposal
from runner_genesis.config import Settings
from runner_genesis.domain.events import MarketEvent, EventType
from runner_genesis.orchestrator import RunnerGenesisOmega, PendingPaperOrder

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def event(event_id='e1', at=T0):
    return MarketEvent(event_id=event_id, timestamp=at, token_mint='M',
                       event_type=EventType.PRICE, price_usd=1, liquidity_usd=100_000)


def config(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'runtime.db'}")


def test_crash_rolls_back_event_and_requires_restart(tmp_path, monkeypatch):
    settings = config(tmp_path)
    engine = RunnerGenesisOmega(settings)
    def fail(_):
        raise OSError('injected persistence failure')
    monkeypatch.setattr(engine.repository, 'record_decision', fail)
    with pytest.raises(OSError):
        engine.process(event())
    assert not engine.repository.has_event('e1')
    assert engine.repository.load_checkpoint() is None
    with pytest.raises(RuntimeError, match='restart required'):
        engine.process(event())
    restarted = RunnerGenesisOmega(settings)
    restarted.process(event())
    assert restarted.repository.has_event('e1')


def test_restart_keeps_equity_peak_and_rejects_old_state(tmp_path):
    settings = config(tmp_path)
    engine = RunnerGenesisOmega(settings)
    engine.portfolio.account.peak_equity_eur = 450
    engine.process(event())
    restarted = RunnerGenesisOmega(settings)
    assert restarted.portfolio.account.peak_equity_eur == 450
    result = restarted.process(event('old', T0 - timedelta(seconds=1)))
    assert result.snapshot.action == 'IGNORED_OUT_OF_ORDER'
    assert 'M' not in restarted.store.tokens


def test_rejected_pending_signal_does_not_resurrect(tmp_path):
    settings = config(tmp_path)
    engine = RunnerGenesisOmega(settings)
    due = T0 + timedelta(seconds=60)
    engine.pending_orders['M'] = PendingPaperOrder(TradeProposal(Action.ENTER, 'M', amount_eur=200), T0, due, {})
    engine.repository.record_paper_update('M', T0, 'PENDING_ENTER', {'due_time': due, 'amount_eur': 200})
    quote = event('quote', due)
    token = engine.store.apply(quote)
    fill, reasons = engine._execute_due_pending('M', due, token, {'entry_validity': 'VALID'}, quote)
    assert fill is None and 'MAX_POSITION' in reasons
    assert 'M' not in RunnerGenesisOmega(settings).pending_orders


def test_pending_expires_without_executable_quote(tmp_path):
    settings = config(tmp_path)
    engine = RunnerGenesisOmega(settings)
    due = T0 + timedelta(seconds=60)
    engine.pending_orders['M'] = PendingPaperOrder(TradeProposal(Action.ENTER, 'M', amount_eur=10), T0, due, {})
    now = due + timedelta(seconds=settings.execution.pending_expiry_seconds + 1)
    fill, reasons = engine._execute_due_pending('M', now, engine.store.token('M'), {'entry_validity': 'VALID'})
    assert fill is None and reasons == ['PENDING_EXPIRED']
    assert not engine.pending_orders


def test_database_dedupe_survives_memory_cache_eviction(tmp_path):
    engine = RunnerGenesisOmega(config(tmp_path))
    engine.process(event())
    engine._processed_event_ids.clear()
    engine._event_result_cache.clear()
    assert engine.process(event()).snapshot.action == 'DUPLICATE_IGNORED'
    assert len(engine.decisions) == 1
