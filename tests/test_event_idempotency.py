from datetime import datetime, timezone

from runner_genesis.config import Settings
from runner_genesis.domain.events import EventType, MarketEvent
from runner_genesis.orchestrator import RunnerGenesisOmega


def sample_event():
    return MarketEvent(
        event_id="same-event",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        token_mint="MintIdempotent111111111111111111111111111111",
        wallet="WalletA",
        event_type=EventType.BUY,
        usd_value=25.0,
        price_usd=0.01,
        market_cap_usd=10_000.0,
        liquidity_usd=20_000.0,
        asset_match_verified=True,
    )


def test_duplicate_event_does_not_double_count_runtime():
    settings = Settings()
    settings.features["database_persistence"] = {"enabled": False}
    engine = RunnerGenesisOmega(settings)
    event = sample_event()

    first = engine.process(event)
    events_before = len(engine.store.token(event.token_mint).events)
    buy_before = engine.store.token(event.token_mint).buy_usd
    decisions_before = len(engine.decisions)

    second = engine.process(event)

    assert second is first
    assert len(engine.store.token(event.token_mint).events) == events_before
    assert engine.store.token(event.token_mint).buy_usd == buy_before
    assert len(engine.decisions) == decisions_before


def test_duplicate_event_is_ignored_after_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'idempotency.db'}"
    settings = Settings(database_url=url)
    settings.features["database_persistence"] = {"enabled": True}
    event = sample_event()

    first_engine = RunnerGenesisOmega(settings)
    first_engine.process(event)

    second_engine = RunnerGenesisOmega(settings)
    result = second_engine.process(event)

    assert result.snapshot.action == "DUPLICATE_IGNORED"
    assert result.risk_approved is False
    assert event.token_mint not in second_engine.store.tokens
