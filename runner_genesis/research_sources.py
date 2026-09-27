from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .ingestion.helius_history import (
    EnhancedWalletHistoryNormalizer,
    HeliusWalletHistoryClient,
    WalletOutcomeBuilder,
)


def _first(mapping: dict[str, Any], *keys: str):
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _rows_from_data(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("rows", "traders", "items", "leaderboard", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


@dataclass
class BackfillResult:
    wallet: str
    transactions: int
    swap_events: int
    funding_links: int
    resolved_outcomes: int
    added_outcomes: int


class WalletResearchBackfillService:
    """Read-only historical wallet qualification service."""

    def __init__(self, client: HeliusWalletHistoryClient, repository=None) -> None:
        self.client = client
        self.repository = repository
        self.normalizer = EnhancedWalletHistoryNormalizer()
        self.outcomes = WalletOutcomeBuilder()

    async def backfill_wallet(self, wallet: str, store, actor, *, limit: int = 100, max_pages: int = 5) -> BackfillResult:
        txs = await self.client.fetch_transactions(wallet, limit=limit, max_pages=max_pages)
        events = []
        funding = []
        for tx in txs:
            events.extend(self.normalizer.normalize_swap(wallet, tx))
            funding.extend(self.normalizer.funding_links(wallet, tx))
        for event in sorted(events, key=lambda x: x.timestamp):
            actor.observe(event)
        for link in sorted(funding, key=lambda x: x.timestamp):
            actor.observe_funding_link(link.wallet, link.funder, link.timestamp, link.confidence)
            if self.repository:
                self.repository.record_funding_relationship(link)
        resolved = self.outcomes.build(events)
        added = store.backfill_wallet_observations(wallet, resolved) if resolved else 0
        if self.repository:
            for obs in resolved:
                self.repository.record_wallet_outcome(wallet, obs)
        return BackfillResult(
            wallet=wallet,
            transactions=len(txs),
            swap_events=len(events),
            funding_links=len(funding),
            resolved_outcomes=len(resolved),
            added_outcomes=added,
        )


class FomoScanPumpProvider:
    """Optional discovery provider for FomoScan's documented Pump leaderboard/feed API.

    Data from this provider is discovery context only. It never bypasses on-chain wallet
    qualification and never becomes a direct trade instruction.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.fomoscan.sh",
        timeout_seconds: float = 15.0,
    ) -> None:
        if not api_key:
            raise ValueError("FOMOSCAN_API_KEY is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}{path}", headers=headers, params=params or {})
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, dict):
            return {"data": body, "meta": {}}
        return body

    async def pump_leaderboard(self) -> tuple[list[dict[str, Any]], datetime]:
        body = await self._get("/v2/pump/leaderboard/traders")
        meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
        raw_at = meta.get("asOf") or meta.get("as_of")
        observed_at = self._parse_time(raw_at)
        rows = []
        for idx, row in enumerate(_rows_from_data(body.get("data"))):
            nested = row.get("user") if isinstance(row.get("user"), dict) else {}
            wallet = _first(row, "wallet", "walletAddress", "wallet_address", "address", "solanaAddress")
            if wallet is None:
                wallet = _first(nested, "wallet", "walletAddress", "address", "solanaAddress")
            if not wallet:
                continue
            rank = _first(row, "rank", "position")
            pnl = _first(row, "monthly_pnl", "monthlyPnl", "realized_pnl", "realizedPnl", "profit", "pnl")
            username = _first(row, "username", "handle", "name") or _first(nested, "username", "handle", "name")
            try:
                rank = int(rank) if rank is not None else idx + 1
            except (TypeError, ValueError):
                rank = idx + 1
            try:
                pnl = float(pnl) if pnl is not None else None
            except (TypeError, ValueError):
                pnl = None
            rows.append({
                "wallet_address": str(wallet),
                "username": str(username) if username is not None else None,
                "rank": rank,
                "monthly_pnl": pnl,
                "source_window": "provider",
                "source_confidence": 0.85,
                "mapping_confidence": 1.0,
            })
        return rows, observed_at

    async def pump_callouts(self, limit: int = 100) -> tuple[list[dict[str, Any]], datetime]:
        body = await self._get("/v2/pump/thesis", params={"limit": max(1, min(int(limit), 100))})
        meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
        observed_at = self._parse_time(meta.get("asOf") or meta.get("as_of"))
        return _rows_from_data(body.get("data")), observed_at

    @staticmethod
    def _parse_time(raw: Any) -> datetime:
        if isinstance(raw, (int, float)):
            value = float(raw)
            if value > 10_000_000_000:
                value /= 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(raw, str):
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)
