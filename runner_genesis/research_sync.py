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
        self._last_backfill: dict[str, datetime] = {}
        self._last_sync: datetime | None = None
        self._last_result: dict[str, Any] = {"status": "NOT_RUN"}

    @property
    def enabled(self) -> bool:
        # FomoScan can discover new Pump wallets automatically. Helius can still refresh
        # wallets that were already discovered/persisted or manually seeded.
        return bool(
            (self.settings.external_discovery.fomoscan_enabled and self.settings.fomoscan_api_key)
            or (self.settings.helius_history.enabled and self.settings.helius_api_key)
        )

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "fomoscan_configured": bool(self.settings.fomoscan_api_key),
            "helius_configured": bool(self.settings.helius_api_key),
            "last_sync": self._last_sync,
            "last_result": self._last_result,
            "tracked_wallets": len(self._seen_wallets),
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
            "metadata": {
                "provider_observed_at": observed_at,
                "raw_id": first("id", "callout_id", "calloutId"),
            },
        }

    def _seed_rows_from_registry(self) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for snap in self.engine.discovery.snapshots:
            current = latest.get(snap.wallet_address)
            if current is None or snap.observed_at > current["observed_at"]:
                latest[snap.wallet_address] = {
                    "wallet_address": snap.wallet_address,
                    "username": snap.username,
                    "rank": snap.rank,
                    "monthly_pnl": snap.monthly_pnl,
                    "source_window": snap.source_window,
                    "source_confidence": snap.source_confidence,
                    "observed_at": snap.observed_at,
                }
        for wallet, sources in self.engine.discovery.wallet_sources.items():
            if wallet in latest:
                continue
            rank = min(
                (x.source_rank for x in sources if x.source_rank is not None),
                default=None,
            )
            latest[wallet] = {
                "wallet_address": wallet,
                "username": next((x.username for x in sources if x.username), None),
                "rank": rank,
                "monthly_pnl": None,
                "source_window": next((x.source_window for x in sources if x.source_window), None),
                "source_confidence": max((x.mapping_confidence for x in sources), default=0.5),
                "observed_at": max(
                    (x.last_verified or x.first_seen for x in sources if (x.last_verified or x.first_seen)),
                    default=datetime.now(timezone.utc),
                ),
            }
        return list(latest.values())

    async def sync_once(self, max_wallets: int | None = None) -> dict[str, Any]:
        if not self.enabled:
            result = {
                "status": "WAITING_CREDENTIALS_OR_DISABLED",
                "fomoscan_configured": bool(self.settings.fomoscan_api_key),
                "helius_configured": bool(self.settings.helius_api_key),
            }
            self._last_result = result
            return result

        rows: list[dict[str, Any]] = []
        observed_at = datetime.now(timezone.utc)
        accepted = 0
        callout_count = 0
        discovery_source = "PERSISTED_OR_MANUAL_REGISTRY"

        fomo_provider_enabled = bool(
            self.settings.external_discovery.fomoscan_enabled
            and self.settings.fomoscan_api_key
        )
        if fomo_provider_enabled:
            provider = FomoScanPumpProvider(
                self.settings.fomoscan_api_key,
                base_url=self.settings.fomoscan_base_url,
            )
            rows, observed_at = await provider.pump_leaderboard()
            discovery_source = "FOMOSCAN_PUMP"
            if self.settings.fomo.enabled:
                try:
                    callouts, callout_observed_at = await provider.pump_callouts(limit=100)
                    for row in callouts:
                        obs = self._callout_observation(row, callout_observed_at)
                        if obs is None:
                            continue
                        ingested = self.engine.fomo.ingest(obs)
                        if ingested is None:
                            continue
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
                    callout_count = 0

            accepted = self.engine.discovery.ingest_leaderboard(
                rows,
                observed_at=observed_at,
                source="PUMPFUN_TOP_TRADER",
            )
            if self.engine.repository and accepted:
                for snap in self.engine.discovery.snapshots[-accepted:]:
                    self.engine.repository.record_leaderboard(snap.__dict__)
        else:
            rows = self._seed_rows_from_registry()
            if rows:
                observed_at = max(
                    (
                        row.get("observed_at")
                        for row in rows
                        if isinstance(row.get("observed_at"), datetime)
                    ),
                    default=observed_at,
                )

        limit = int(max_wallets or self.settings.external_discovery.max_wallets_per_refresh)
        ranked = sorted(
            rows,
            key=lambda x: (
                int(x.get("rank") or 10**9),
                -(float(x.get("monthly_pnl") or 0.0)),
            ),
        )[: max(0, limit)]

        backfills = []
        skipped_recent = 0
        if self.settings.helius_history.enabled and self.settings.helius_api_key and ranked:
            client = HeliusWalletHistoryClient(self.settings.helius_api_key)
            service = WalletResearchBackfillService(client, repository=self.engine.repository)
            now = datetime.now(timezone.utc)
            min_age = max(60.0, float(self.settings.helius_history.refresh_seconds))
            due_wallets = []
            for row in ranked:
                wallet = str(row.get("wallet_address") or "").strip()
                if not wallet:
                    continue
                previous = self._last_backfill.get(wallet)
                if previous is not None and (now - previous).total_seconds() < min_age:
                    skipped_recent += 1
                    continue
                due_wallets.append(wallet)

            semaphore = asyncio.Semaphore(max(1, int(self.settings.helius_history.max_concurrency)))

            async def run_one(wallet: str):
                async with semaphore:
                    try:
                        result = await service.backfill_wallet(
                            wallet,
                            self.engine.store,
                            self.engine.actor,
                            limit=self.settings.helius_history.page_limit,
                            max_pages=self.settings.helius_history.max_pages,
                        )
                        self._seen_wallets.add(wallet)
                        self._last_backfill[wallet] = now
                        return asdict(result)
                    except Exception as exc:
                        return {
                            "wallet": wallet,
                            "error": type(exc).__name__,
                            "message": str(exc)[:200],
                        }

            if due_wallets:
                backfills = list(await asyncio.gather(*(run_one(w) for w in due_wallets)))

        self._last_sync = datetime.now(timezone.utc)
        status = "OK"
        if not rows:
            status = "WAITING_DISCOVERY_SOURCE"
        self._last_result = {
            "status": status,
            "discovery_source": discovery_source,
            "observed_at": observed_at,
            "leaderboard_rows": len(rows),
            "accepted_snapshots": accepted,
            "fomo_callouts_ingested": callout_count,
            "wallet_backfills": backfills,
            "wallet_backfills_skipped_recent": skipped_recent,
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
