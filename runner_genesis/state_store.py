from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from .domain.events import MarketEvent, EventType
from .domain.state import TokenState, WalletState, WalletBuyObservation
from .point_in_time import PointInTimeSeries


BUY_TYPES = {
    EventType.BUY,
    EventType.DEV_BUY,
    EventType.RUNNER_HOLDER_ENTRY,
    EventType.RUNNER_HOLDER_ADD,
    EventType.SMART_WALLET_NEW_ENTRY,
    EventType.SMART_WALLET_ADD,
}
SELL_TYPES = {
    EventType.SELL,
    EventType.DEV_SELL,
    EventType.RUNNER_HOLDER_REDUCE,
    EventType.RUNNER_HOLDER_EXIT,
    EventType.SMART_WALLET_REDUCE,
    EventType.SMART_WALLET_EXIT,
}


class MarketStateStore:
    def __init__(self, max_token_events: int = 5000) -> None:
        self.tokens: dict[str, TokenState] = {}
        self.wallets: dict[str, WalletState] = {}
        self.wallet_resolved_history: dict[str, PointInTimeSeries[WalletBuyObservation]] = defaultdict(PointInTimeSeries)
        self.max_token_events = max_token_events

    def token(self, mint: str) -> TokenState:
        return self.tokens.setdefault(mint, TokenState(token_mint=mint))

    def wallet(self, address: str) -> WalletState:
        return self.wallets.setdefault(address, WalletState(wallet=address))

    def apply(self, e: MarketEvent) -> TokenState:
        t = self.token(e.token_mint)
        if t.first_seen_at is None:
            t.first_seen_at = e.timestamp
        t.last_event_at = e.timestamp
        if e.event_type == EventType.TOKEN_CREATED and t.created_at is None:
            t.created_at = e.timestamp
            t.creation_evidence_source = e.source
            t.age_confidence = float(e.confidence)
        if e.event_type == EventType.MIGRATION and t.migration_at is None:
            t.migration_at = e.timestamp
        if e.price_usd is not None:
            t.price_usd = e.price_usd
        if e.market_cap_usd is not None:
            t.market_cap_usd = e.market_cap_usd
        if e.liquidity_usd is not None:
            t.liquidity_usd = e.liquidity_usd

        # Risk metadata can be attached by normalizers/adapters. Unknown stays None.
        for key in ("dev_holdings_pct", "sniper_pct", "bundle_pct", "suspected_related_concentration_pct"):
            if key in e.metadata and e.metadata[key] is not None:
                setattr(t, key, float(e.metadata[key]))
        for key in ("observed_holder_count", "real_holder_count"):
            if key in e.metadata and e.metadata[key] is not None:
                setattr(t, key, int(e.metadata[key]))
        # Preserve point-in-time metadata that downstream engines may need.
        for key in (
            "mint_authority_active", "freeze_authority_active", "wash_score",
            "sellability_score", "deployer_risk_score", "protocol", "launchpad",
            "pool_address", "bundle_count", "sniper_count",
        ):
            if key in e.metadata and e.metadata[key] is not None:
                t.metadata[key] = e.metadata[key]

        if e.wallet:
            w = self.wallet(e.wallet)
            if w.first_seen is None:
                w.first_seen = e.timestamp
            w.last_seen = e.timestamp
            if e.event_type in BUY_TYPES:
                size = float(e.usd_value or 0.0)
                w.buys.append((e.timestamp, size, e.market_cap_usd))
                t.buyers.add(e.wallet)
                t.buy_usd += size
            elif e.event_type in SELL_TYPES:
                size = float(e.usd_value or 0.0)
                w.sells.append((e.timestamp, size))
                t.sellers.add(e.wallet)
                t.sell_usd += size
            elif e.event_type == EventType.WALLET_FUNDED:
                w.funded_events.append((e.timestamp, float(e.usd_value or 0.0), e.counterparty))
            elif e.event_type == EventType.TRANSFER:
                direction = "IN" if e.wallet else "UNKNOWN"
                w.transfers.append((e.timestamp, e.usd_value, e.counterparty, direction))

        t.events.append(e)
        if len(t.events) > self.max_token_events:
            del t.events[: len(t.events) - self.max_token_events]
        return t

    def resolve_wallet_observation(self, wallet: str, obs: WalletBuyObservation) -> None:
        self.wallet_resolved_history[wallet].add(obs.resolved_at, obs)

    def backfill_wallet_observations(self, wallet: str, observations: list[WalletBuyObservation]) -> int:
        """Merge historical resolved outcomes while preserving point-in-time ordering.

        Backfills can legitimately contain observations older than values already loaded in
        memory. Rebuilding the small per-wallet series avoids weakening PointInTimeSeries'
        chronological append invariant for normal live ingestion.
        """
        existing = self.wallet_resolved_history[wallet].values_as_of(datetime.max.replace(tzinfo=observations[0].resolved_at.tzinfo) if observations else datetime.max)
        merged: dict[tuple, WalletBuyObservation] = {}
        for obs in [*existing, *observations]:
            key = (obs.token_mint, obs.event_time, obs.resolved_at)
            merged[key] = obs
        series = PointInTimeSeries[WalletBuyObservation]()
        for obs in sorted(merged.values(), key=lambda x: (x.resolved_at, x.event_time, x.token_mint)):
            series.add(obs.resolved_at, obs)
        added = max(0, len(merged) - len(existing))
        self.wallet_resolved_history[wallet] = series
        return added

    def resolved_wallet_history_as_of(self, wallet: str, as_of: datetime) -> list[WalletBuyObservation]:
        return self.wallet_resolved_history[wallet].values_as_of(as_of)
