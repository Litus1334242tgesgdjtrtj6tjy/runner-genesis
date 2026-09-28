from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Any
from pydantic import BaseModel, Field, field_validator


class EventType(StrEnum):
    TOKEN_CREATED = "TOKEN_CREATED"
    BUY = "BUY"
    SELL = "SELL"
    SWAP = "SWAP"
    TRANSFER = "TRANSFER"
    WALLET_FUNDED = "WALLET_FUNDED"
    LIQUIDITY_ADDED = "LIQUIDITY_ADDED"
    LIQUIDITY_REMOVED = "LIQUIDITY_REMOVED"
    MIGRATION = "MIGRATION"
    HOLDER_CREATED = "HOLDER_CREATED"
    DEV_TRANSFER = "DEV_TRANSFER"
    DEV_BUY = "DEV_BUY"
    DEV_SELL = "DEV_SELL"
    RUNNER_HOLDER_ENTRY = "RUNNER_HOLDER_ENTRY"
    RUNNER_HOLDER_ADD = "RUNNER_HOLDER_ADD"
    RUNNER_HOLDER_REDUCE = "RUNNER_HOLDER_REDUCE"
    RUNNER_HOLDER_EXIT = "RUNNER_HOLDER_EXIT"
    CLUSTER_ACTIVITY = "CLUSTER_ACTIVITY"
    SMART_WALLET_NEW_ENTRY = "SMART_WALLET_NEW_ENTRY"
    SMART_WALLET_ADD = "SMART_WALLET_ADD"
    SMART_WALLET_REDUCE = "SMART_WALLET_REDUCE"
    SMART_WALLET_EXIT = "SMART_WALLET_EXIT"
    PRICE = "PRICE"


class MarketEvent(BaseModel):
    event_id: str
    timestamp: datetime
    slot: int | None = None
    tx_signature: str | None = None
    token_mint: str
    wallet: str | None = None
    counterparty: str | None = None
    actor_id: str | None = None
    event_type: EventType
    event_subtype: str | None = None
    amount_token: float | None = None
    sol_value: float | None = None
    usd_value: float | None = None
    price_usd: float | None = None
    market_cap_usd: float | None = None
    liquidity_usd: float | None = None
    token_age_seconds: float | None = None
    source: str = "normalized"
    confidence: float = 1.0
    data_quality_score: float | None = None
    asset_match_verified: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("confidence", "data_quality_score")
    @classmethod
    def valid_unit_interval(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not math.isfinite(v):
            raise ValueError("quality/confidence must be finite")
        return min(1.0, max(0.0, v))

    @field_validator("price_usd", "market_cap_usd", "liquidity_usd", "amount_token", "sol_value", "usd_value")
    @classmethod
    def nonnegative_finite(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("market amounts must be finite and nonnegative")
        return value


class DecisionSnapshot(BaseModel):
    decision_time: datetime
    token_mint: str
    feature_version: str = "v0.2"
    model_version: str = "untrained-baseline"
    data_available_until: datetime
    features: dict[str, float | int | str | bool | None]
    probabilities: dict[str, float | None]
    action: str
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
