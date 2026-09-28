from datetime import datetime, timedelta, timezone

from runner_genesis.db import RuntimeRepository
from runner_genesis.domain.events import EventType, MarketEvent
from runner_genesis.engines.actor_graph import ActorGraphEngine
from runner_genesis.research_sources import WalletResearchBackfillService, WalletResearchBundle
from runner_genesis.state_store import MarketStateStore


class _NoopClient:
    pass


def _event(event_id, ts, typ, amount_token, quote_value):
    return MarketEvent(
        event_id=event_id,
        timestamp=ts,
        token_mint="M",
        wallet="W",
        event_type=typ,
        amount_token=amount_token,
        sol_value=quote_value,
        source="history",
        asset_match_verified=True,
        metadata={"quote_asset": "SOL", "quote_value": quote_value},
    )


def test_wallet_outcome_rebuild_crosses_pagination_boundary(tmp_path):
    repo = RuntimeRepository(f"sqlite:///{tmp_path / 'history.db'}")
    service = WalletResearchBackfillService(_NoopClient(), repository=repo)
    store = MarketStateStore()
    actor = ActorGraphEngine()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Newest page arrives first and contains a SELL whose BUY is not fetched yet.
    sell = _event("sell", t0 + timedelta(hours=2), EventType.SELL, 100.0, 2.0)
    page_new = WalletResearchBundle(
        wallet="W",
        transactions=[],
        events=[sell],
        funding_links=[],
        outcomes=[],
        history_exhausted=False,
    )
    first = service.apply_bundle(page_new, store, actor)
    assert first.resolved_outcomes == 0
    assert store.resolved_wallet_history_as_of("W", t0 + timedelta(hours=3)) == []

    # Older continuation page supplies the matching BUY. Rebuilding from persisted
    # normalized wallet events must now resolve the complete cycle.
    buy = _event("buy", t0, EventType.BUY, 100.0, 1.0)
    page_old = WalletResearchBundle(
        wallet="W",
        transactions=[],
        events=[buy],
        funding_links=[],
        outcomes=[],
        history_exhausted=True,
    )
    second = service.apply_bundle(page_old, store, actor)
    assert second.resolved_outcomes == 1
    outcomes = store.resolved_wallet_history_as_of("W", t0 + timedelta(hours=3))
    assert len(outcomes) == 1
    assert abs(outcomes[0].realized_return - 1.0) < 1e-12

    # Re-applying either page is idempotent in both transaction DB and outcome store.
    service.apply_bundle(page_old, store, actor)
    service.apply_bundle(page_new, store, actor)
    outcomes2 = store.resolved_wallet_history_as_of("W", t0 + timedelta(hours=3))
    assert len(outcomes2) == 1
