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
