from datetime import datetime, timezone, timedelta

from runner_genesis.config import PumpDiscoveryConfig
from runner_genesis.domain.events import EventType, MarketEvent
from runner_genesis.engines.actor_graph import ActorGraphEngine
from runner_genesis.engines.discovery import PumpDiscoveryEngine


def test_top_trader_wave_uses_effective_wallets_and_recent_arrivals():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    discovery = PumpDiscoveryEngine(PumpDiscoveryConfig())
    rows = [
        {"wallet_address": "A", "rank": 1, "monthly_pnl": 1000},
        {"wallet_address": "B", "rank": 2, "monthly_pnl": 900},
        {"wallet_address": "C", "rank": 3, "monthly_pnl": 800},
    ]
    assert discovery.ingest_leaderboard(rows, observed_at=t0, source="PUMPFUN_TOP_TRADER") == 3

    actor = ActorGraphEngine()
    for i, wallet in enumerate(["A", "B", "C"]):
        actor.observe_funding_link(wallet, "COMMON_FUNDER", t0 + timedelta(seconds=i), 0.95)

    events = [
        MarketEvent(
            event_id=f"b{i}",
            timestamp=t0 + timedelta(seconds=10 + i * 5),
            token_mint="MINT",
            wallet=wallet,
            event_type=EventType.BUY,
            usd_value=100,
        )
        for i, wallet in enumerate(["A", "B", "C"])
    ]
    now = t0 + timedelta(seconds=40)
    features = discovery.token_wave_features(
        ["A", "B", "C"],
        now,
        actor=actor,
        events=events,
    )
    assert features["top_trader_count"] == 3
    assert features["top_trader_effective_count"] < 3
    assert features["top_trader_independence_ratio"] < 1
    assert features["new_top_traders_30s"] >= 1
    assert features["new_top_traders_60s"] == 3
    assert 0 <= features["top_trader_wave_score"] <= 1
