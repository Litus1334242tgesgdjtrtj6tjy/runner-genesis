from datetime import datetime, timedelta, timezone

from runner_genesis.config import Settings
from runner_genesis.db import RuntimeRepository
from runner_genesis.domain.events import EventType, MarketEvent
from runner_genesis.orchestrator import RunnerGenesisOmega


def _event(event_id, ts, typ, token_amount, usd, price):
    return MarketEvent(
        event_id=event_id,
        timestamp=ts,
        token_mint="M",
        wallet="W",
        event_type=typ,
        amount_token=token_amount,
        usd_value=usd,
        price_usd=price,
        asset_match_verified=True,
        source="test_history",
    )


def test_persisted_wallet_transactions_rebuild_position_after_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'wallet_tx.db'}"
    repo = RuntimeRepository(url)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        _event("b1", t0, EventType.BUY, 100.0, 100.0, 1.0),
        _event("b2", t0 + timedelta(minutes=10), EventType.BUY, 100.0, 200.0, 2.0),
        _event("s1", t0 + timedelta(minutes=20), EventType.SELL, 100.0, 150.0, 1.5),
    ]
    # Persistence order must not matter; loader orders chronologically.
    for event in reversed(events):
        repo.record_wallet_transaction(event)

    settings = Settings(database_url=url)
    settings.features["database_persistence"] = {"enabled": True}
    engine = RunnerGenesisOmega(settings)

    p = engine.smart.positions[("W", "M")]
    assert p.first_entry_time == t0
    assert p.last_activity_time == t0 + timedelta(minutes=20)
    assert p.buy_count == 2
    assert p.sell_count == 1
    assert abs(p.retained_fraction - 0.5) < 1e-12
    assert abs(p.average_entry_price - (5.0 / 3.0)) < 1e-12

    # A second process hydration remains idempotent.
    engine2 = RunnerGenesisOmega(settings)
    p2 = engine2.smart.positions[("W", "M")]
    assert p2.buy_count == 2
    assert p2.sell_count == 1
