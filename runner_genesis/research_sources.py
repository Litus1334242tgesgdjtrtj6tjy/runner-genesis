from __future__ import annotations

from dataclasses import dataclass
import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any

import httpx

from .domain.events import MarketEvent
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
    oldest_transaction_at: datetime | None = None
    requested_stop_before: datetime | None = None
    history_target_reached: bool = False
    history_exhausted: bool = False
    next_before_signature: str | None = None


@dataclass
class WalletResearchBundle:
    wallet: str
    transactions: list[dict[str, Any]]
    events: list[Any]
    funding_links: list[Any]
    outcomes: list[Any]
    requested_stop_before: datetime | None = None
    oldest_transaction_at: datetime | None = None
    start_before_signature: str | None = None
    oldest_signature: str | None = None
    history_exhausted: bool = False


class WalletResearchBackfillService:
    """Read-only historical wallet qualification service.

    Fetch/normalize is separated from mutation so the coordinator can merge several wallet
    histories chronologically before feeding the Actor Graph. This prevents concurrency or
    wallet-fetch order from manufacturing/coarsening co-buy relationships.
    """

    def __init__(
        self,
        client: HeliusWalletHistoryClient,
        repository=None,
        *,
        min_funding_sol: float = 0.01,
    ) -> None:
        self.client = client
        self.repository = repository
        self.min_funding_sol = max(0.0, float(min_funding_sol))
        self.normalizer = EnhancedWalletHistoryNormalizer()
        self.outcomes = WalletOutcomeBuilder()

    async def fetch_wallet_bundle(
        self,
        wallet: str,
        *,
        limit: int = 100,
        max_pages: int = 5,
        stop_before_time: datetime | None = None,
        before: str | None = None,
    ) -> WalletResearchBundle:
        fetch_kwargs = {
            "limit": limit,
            "max_pages": max_pages,
            "stop_before_time": stop_before_time,
            "before": before,
        }
        try:
            params = inspect.signature(self.client.fetch_transactions).parameters
            supports_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
            )
            if not supports_kwargs:
                fetch_kwargs = {k: v for k, v in fetch_kwargs.items() if k in params}
        except (TypeError, ValueError):
            pass
        txs = await self.client.fetch_transactions(wallet, **fetch_kwargs)
        events = []
        funding = []
        for tx in txs:
            events.extend(self.normalizer.normalize_swap(wallet, tx))
            funding.extend(self.normalizer.funding_links(wallet, tx, min_sol=self.min_funding_sol))
        events.sort(key=lambda x: x.timestamp)
        funding.sort(key=lambda x: x.timestamp)
        resolved = self.outcomes.build(events)
        tx_times = []
        for tx in txs:
            if not isinstance(tx, dict):
                continue
            raw = tx.get("timestamp") or tx.get("blockTime")
            ts = None
            if isinstance(raw, (int, float)):
                ts = datetime.fromtimestamp(float(raw), tz=timezone.utc)
            elif isinstance(raw, str):
                try:
                    ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except ValueError:
                    ts = None
            if ts is not None:
                tx_times.append(ts)
        oldest = min(tx_times) if tx_times else None
        capacity = max(1, int(limit)) * max(1, int(max_pages))
        history_exhausted = (
            (before is not None and len(txs) == 0)
            or len(txs) < capacity
        )
        return WalletResearchBundle(
            wallet=wallet,
            transactions=txs,
            events=events,
            funding_links=funding,
            outcomes=resolved,
            requested_stop_before=stop_before_time,
            oldest_transaction_at=oldest,
            start_before_signature=before,
            oldest_signature=(str(txs[-1].get("signature")) if txs and txs[-1].get("signature") else None),
            history_exhausted=history_exhausted,
        )

    def apply_bundle(
        self,
        bundle: WalletResearchBundle,
        store,
        actor,
        *,
        smart=None,
        apply_actor_events: bool = True,
        apply_funding: bool = True,
    ) -> BackfillResult:
        if apply_actor_events:
            if hasattr(actor, "observe_historical_batch"):
                actor.observe_historical_batch(bundle.events)
            else:
                for event in bundle.events:
                    actor.observe(event)
        if apply_funding:
            for link in bundle.funding_links:
                actor.observe_funding_link(link.wallet, link.funder, link.timestamp, link.confidence)

        if smart is not None and hasattr(smart, "observe_historical_batch"):
            smart.observe_historical_batch(bundle.events)

        replay_events = list(bundle.events)
        resolved_outcomes = list(bundle.outcomes)
        if self.repository:
            for event in bundle.events:
                if hasattr(self.repository, "record_wallet_transaction"):
                    self.repository.record_wallet_transaction(event)

            # Rebuild closed trade cycles across page boundaries. A BUY can live in an
            # older continuation page while its SELL was fetched earlier; resolving each
            # page in isolation would silently miss exactly those wallet outcomes.
            if hasattr(self.repository, "load_wallet_transactions"):
                replay_events = []
                for row in self.repository.load_wallet_transactions(
                    limit=500_000,
                    wallet_address=bundle.wallet,
                ):
                    payload = row.get("payload")
                    if not isinstance(payload, dict):
                        continue
                    try:
                        replay_events.append(MarketEvent.model_validate(payload))
                    except Exception:
                        continue
                if replay_events:
                    resolved_outcomes = self.outcomes.build(replay_events)

        if smart is not None and hasattr(smart, "observe_historical_batch") and replay_events:
            smart.observe_historical_batch(replay_events)

        added = (
            store.backfill_wallet_observations(bundle.wallet, resolved_outcomes)
            if resolved_outcomes else 0
        )
        if self.repository:
            for link in bundle.funding_links:
                self.repository.record_funding_relationship(link)
            for obs in resolved_outcomes:
                self.repository.record_wallet_outcome(bundle.wallet, obs)
            if smart is not None and replay_events:
                latest_by_mint: dict[str, datetime] = {}
                for event in replay_events:
                    current = latest_by_mint.get(event.token_mint)
                    if current is None or event.timestamp > current:
                        latest_by_mint[event.token_mint] = event.timestamp
                for mint, observed_at in latest_by_mint.items():
                    snapshot = smart.position_snapshot(bundle.wallet, mint, observed_at)
                    if snapshot:
                        self.repository.record_wallet_position(bundle.wallet, mint, observed_at, snapshot)

        target = bundle.requested_stop_before
        oldest = bundle.oldest_transaction_at
        target_reached = bool(
            bundle.history_exhausted
            or (
                target is not None
                and oldest is not None
                and oldest <= (target if target.tzinfo else target.replace(tzinfo=timezone.utc))
            )
        )
        return BackfillResult(
            wallet=bundle.wallet,
            transactions=len(bundle.transactions),
            swap_events=len(bundle.events),
            funding_links=len(bundle.funding_links),
            resolved_outcomes=len(resolved_outcomes),
            added_outcomes=added,
            oldest_transaction_at=oldest,
            requested_stop_before=target,
            history_target_reached=target_reached,
            history_exhausted=bool(bundle.history_exhausted),
            next_before_signature=(None if target_reached else bundle.oldest_signature),
        )

    async def backfill_wallet(
        self,
        wallet: str,
        store,
        actor,
        *,
        smart=None,
        limit: int = 100,
        max_pages: int = 5,
        stop_before_time: datetime | None = None,
        before: str | None = None,
    ) -> BackfillResult:
        bundle = await self.fetch_wallet_bundle(
            wallet,
            limit=limit,
            max_pages=max_pages,
            stop_before_time=stop_before_time,
            before=before,
        )
        return self.apply_bundle(bundle, store, actor, smart=smart)


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
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("FOMOSCAN_API_KEY is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = max(0, int(max_retries))

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = None
            for attempt in range(self.max_retries + 1):
                response = await client.get(f"{self.base_url}{path}", headers=headers, params=params or {})
                retryable = response.status_code == 429 or 500 <= response.status_code < 600
                if retryable and attempt < self.max_retries:
                    raw = response.headers.get("retry-after")
                    try:
                        wait = float(raw) if raw is not None else 0.5 * (2 ** attempt)
                    except (TypeError, ValueError):
                        wait = 0.5 * (2 ** attempt)
                    await asyncio.sleep(max(0.1, min(8.0, wait)))
                    continue
                response.raise_for_status()
                break
        if response is None:
            raise RuntimeError("FomoScan request did not return a response")
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
