from datetime import datetime, timezone, timedelta
from pathlib import Path

from runner_genesis.config import load_settings
from runner_genesis.orchestrator import RunnerGenesisOmega, PendingPaperOrder
from runner_genesis.ai_trader import TradeProposal, Action
from runner_genesis.domain.events import MarketEvent, EventType


def test_delayed_entry_preserves_signal_time_cluster_identity(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    settings = load_settings("config/default.yaml")
    settings.features["database_persistence"] = {"enabled": False}
    engine = RunnerGenesisOmega(settings)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    due = t0 + timedelta(seconds=settings.execution.execution_delay_seconds)

    engine.pending_orders["M"] = PendingPaperOrder(
        TradeProposal(Action.ENTER, "M", amount_eur=10),
        t0,
        due,
        {
            "dominant_actor_cluster_id": "actor-cluster-signal",
            "dominant_actor_cluster_fraction": 0.8,
        },
    )

    event = MarketEvent(
        event_id="cluster-q",
        timestamp=due,
        token_mint="M",
        event_type=EventType.PRICE,
        price_usd=1.0,
        liquidity_usd=100_000,
        market_cap_usd=100_000,
        asset_match_verified=True,
    )
    token = engine.store.apply(event)
    fill, reasons = engine._execute_due_pending(
        "M",
        due,
        token,
        {
            "entry_validity": "VALID",
            "sellability_score": 1.0,
            "manipulation_risk": 0.0,
            "dominant_actor_cluster_id": None,
            "dominant_actor_cluster_fraction": 0.0,
        },
        market_event=event,
    )

    assert fill is not None
    assert fill.risk_cluster_id == "actor-cluster-signal"
    assert fill.risk_cluster_fraction == 0.8
    assert engine.portfolio.account.positions["M"].risk_cluster_id == "actor-cluster-signal"
