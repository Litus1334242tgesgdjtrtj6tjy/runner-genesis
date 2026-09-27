from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any


@dataclass
class WalletBuyObservation:
    event_time: datetime
    resolved_at: datetime
    token_mint: str
    buy_eur: float
    entry_mc: float | None = None
    realized_return: float | None = None
    runner_capture_ratio: float | None = None
    hold_seconds: float | None = None


@dataclass
class WalletState:
    wallet: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    buys: list[tuple[datetime, float, float | None]] = field(default_factory=list)
    sells: list[tuple[datetime, float]] = field(default_factory=list)
    transfers: list[tuple[datetime, float | None, str | None, str]] = field(default_factory=list)
    funded_events: list[tuple[datetime, float, str | None]] = field(default_factory=list)


@dataclass
class TokenState:
    token_mint: str
    created_at: datetime | None = None
    migration_at: datetime | None = None
    first_seen_at: datetime | None = None
    creation_evidence_source: str | None = None
    age_confidence: float | None = None
    last_event_at: datetime | None = None
    price_usd: float | None = None
    market_cap_usd: float | None = None
    liquidity_usd: float | None = None
    dev_holdings_pct: float | None = None
    sniper_pct: float | None = None
    bundle_pct: float | None = None
    suspected_related_concentration_pct: float | None = None
    observed_holder_count: int | None = None
    real_holder_count: int | None = None
    buyers: set[str] = field(default_factory=set)
    sellers: set[str] = field(default_factory=set)
    buy_usd: float = 0.0
    sell_usd: float = 0.0
    events: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperPosition:
    token_mint: str
    quantity: float
    avg_entry_price: float
    cost_basis_eur: float
    opened_at: datetime
    last_updated_at: datetime
    realized_pnl_eur: float = 0.0
    adds: int = 0
    moonbag_locked_fraction: float = 0.0


@dataclass
class PaperAccount:
    starting_cash_eur: float
    cash_eur: float
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    realized_pnl_eur: float = 0.0
    daily_spend_eur: float = 0.0
    daily_realized_pnl_eur: float = 0.0
    accounting_day_utc: date | None = None
    peak_equity_eur: float = 0.0
    equity_eur: float = 0.0

    def __post_init__(self) -> None:
        self.peak_equity_eur = self.starting_cash_eur
        self.equity_eur = self.starting_cash_eur

    def advance_accounting_day(self, at: datetime) -> None:
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        day = at.astimezone(timezone.utc).date()
        if self.accounting_day_utc != day:
            self.accounting_day_utc = day
            self.daily_spend_eur = 0.0
            self.daily_realized_pnl_eur = 0.0
