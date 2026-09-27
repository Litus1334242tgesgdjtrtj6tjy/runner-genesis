from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .ingestion.helius_history import HeliusWalletHistoryClient
from .research_sources import FomoScanPumpProvider, WalletResearchBackfillService


class ResearchSyncCoordinator:
    """Optional read-only discovery/backfill coordinator.

    It never submits trades. Its only job is to refresh discovery sources and enrich the
    point-in-time wallet/actor research state used by PAPER/SHADOW modes.
    """

    def __init__(self, settings, engine) -> None:
        self.settings = settings
        self.engine = engine
        self._seen_wallets: set[str] = set()
        self._last_sync: datetime | None = None
        self._last_result: dict[str, Any] = {"status": "NOT_RUN"}

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.external_discovery.fomoscan_enabled
            and self.settings.fomoscan_api_key
        )

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "fomoscan_configured": bool(self.settings.fomoscan_api_key),
            "helius_configured": bool(self.settings.helius_api_key),
            "last_sync": self._last_sync,
            "last_result": self._last_result,
        }


    @staticmethod
    def _callout_observation(row: dict[str, Any], observed_at: datetime) -> dict[str, Any] | None:
        def first(*keys):
            for key in keys:
                value = row.get(key)
                if value is not None:
                    return value
            return None
        token = first("token_mint", "tokenMint", "token_address", "tokenAddress", "mint", "contract")
        nested_token = row.get("token") if isinstance(row.get("token"), dict) else {}
        if not token:
            for key in ("mint", "address", "tokenAddress", "token_address"):
                if nested_token.get(key):
                    token = nested_token[key]
                    break
        if not token:
            return None
        actor = first("wallet", "wallet_address", "walletAddress", "author", "handle", "user_id", "userId")
        nested_user = row.get("user") if isinstance(row.get("user"), dict) else {}
        if not actor:
            actor = nested_user.get("wallet") or nested_user.get("handle") or nested_user.get("id")
        raw_ts = first("timestamp", "created_at", "createdAt", "published_at", "publishedAt")
        ts = observed_at
        if isinstance(raw_ts, (int, float)):
            value = float(raw_ts)
            if value > 10_000_000_000:
                value /= 1000.0
            ts = datetime.fromtimestamp(value, tz=timezone.utc)
        elif isinstance(raw_ts, str):
            try:
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                ts = observed_at
        return {
            "token_mint": str(token),
            "timestamp": ts,
            "source": "FOMOSCAN_PUMP_CALLOUT",
            "kind": "PUMP_CALLOUT",
            "confidence": 0.75,
            "actor_key": str(actor) if actor is not None else None,
            "metadata": {"provider_observed_at": observed_at, "raw_id": first("id", "callout_id", "calloutId")},
        }

    async def sync_once(self, max_wallets: int | None = None) -> dict[str, Any]:
        if not self.enabled:
            result = {
                "status": "WAITING_CREDENTIALS_OR_DISABLED",
                "fomoscan_configured": bool(self.settings.fomoscan_api_key),
                "helius_configured": bool(self.settings.helius_api_key),
            }
            self._last_result = result
            return result

        provider = FomoScanPumpProvider(
            self.settings.fomoscan_api_key,
            base_url=self.settings.fomoscan_base_url,
        )
        rows, observed_at = await provider.pump_leaderboard()
        callout_count = 0
        if self.settings.fomo.enabled:
            try:
                callouts, callout_observed_at = await provider.pump_callouts(limit=100)
                for row in callouts:
                    obs = self._callout_observation(row, callout_observed_at)
                    if obs is None:
                        continue
                    self.engine.fomo.ingest(obs)
                    callout_count += 1
                    if self.engine.repository:
                        self.engine.repository.record_discovery({
                            "token_mint": obs["token_mint"],
                            "wallet_address": None,
                            "observed_at": obs["timestamp"],
                            "source": obs["source"],
                            "kind": obs["kind"],
                            "actor_key": obs["actor_key"],
                        })
            except Exception:
                # Leaderboard sync remains usable even if the optional callout feed changes.
                callout_count = 0

        accepted = self.engine.discovery.ingest_leaderboard(
            rows,
            observed_at=observed_at,
            source="PUMPFUN_TOP_TRADER",
        )
        if self.engine.repository and accepted:
            for snap in self.engine.discovery.snapshots[-accepted:]:
                self.engine.repository.record_leaderboard(snap.__dict__)

        limit = int(max_wallets or self.settings.external_discovery.max_wallets_per_refresh)
        ranked = sorted(
            rows,
            key=lambda x: (
                int(x.get("rank") or 10**9),
                -(float(x.get("monthly_pnl") or 0.0)),
            ),
        )[: max(0, limit)]

        backfills = []
        if self.settings.helius_history.enabled and self.settings.helius_api_key:
            client = HeliusWalletHistoryClient(self.settings.helius_api_key)
            service = WalletResearchBackfillService(client)
            for row in ranked:
                wallet = str(row.get("wallet_address") or "").strip()
                if not wallet:
                    continue
                try:
                    result = await service.backfill_wallet(
                        wallet,
                        self.engine.store,
                        self.engine.actor,
                        limit=self.settings.helius_history.page_limit,
                        max_pages=self.settings.helius_history.max_pages,
                    )
                    backfills.append(asdict(result))
                    self._seen_wallets.add(wallet)
                except Exception as exc:
                    backfills.append({
                        "wallet": wallet,
                        "error": type(exc).__name__,
                        "message": str(exc)[:200],
                    })

        self._last_sync = datetime.now(timezone.utc)
        self._last_result = {
            "status": "OK",
            "observed_at": observed_at,
            "leaderboard_rows": len(rows),
            "accepted_snapshots": accepted,
            "fomo_callouts_ingested": callout_count,
            "wallet_backfills": backfills,
        }
        return self._last_result

    async def run_loop(self, stop_event: asyncio.Event) -> None:
        interval = max(60.0, float(self.settings.external_discovery.refresh_seconds))
        while not stop_event.is_set():
            try:
                await self.sync_once()
            except Exception as exc:
                self._last_result = {
                    "status": "ERROR",
                    "error": type(exc).__name__,
                    "message": str(exc)[:300],
                }
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
