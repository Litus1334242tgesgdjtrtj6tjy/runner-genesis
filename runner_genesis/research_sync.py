from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .ingestion.helius_history import HeliusWalletHistoryClient
from .research_sources import FomoScanPumpProvider, WalletResearchBackfillService
from .engines.wallet_discovery_priority import WalletDiscoveryPriorityEngine


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
        self.wallet_priority = WalletDiscoveryPriorityEngine(settings.external_discovery)
        self._hydrate_backfill_status()

    @staticmethod
    def _aware(ts: datetime) -> datetime:
        return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)

    def _hydrate_backfill_status(self) -> None:
        repository = getattr(self.engine, "repository", None)
        if repository is None or not hasattr(repository, "load_wallet_backfill_status"):
            return
        try:
            rows = repository.load_wallet_backfill_status(
                limit=max(1, int(self.settings.helius_history.hydrate_max_rows))
            )
        except Exception:
            return
        for row in rows:
            wallet = str(row.get("wallet_address") or "").strip()
            ts = row.get("last_success_at")
            if wallet and isinstance(ts, datetime):
                self._last_backfill[wallet] = self._aware(ts)
                self._seen_wallets.add(wallet)

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
                "discovery_kind": "SEEDED_REGISTRY",
            }

        # Helius-only mode can discover candidates organically from live Pump/PumpSwap
        # traffic. These wallets are NOT promoted to top-trader status; they are merely
        # queued for historical qualification so Emerging Smart Wallet can learn them.
        store = getattr(self.engine, "store", None)
        for wallet, state in (getattr(store, "wallets", {}) or {}).items():
            observed = state.last_seen or state.first_seen or datetime.now(timezone.utc)
            current = latest.get(wallet)
            if current is not None and current.get("observed_at") and current["observed_at"] >= observed:
                continue
            latest[wallet] = {
                "wallet_address": wallet,
                "username": None,
                "rank": None,
                "monthly_pnl": None,
                "source_window": None,
                "source_confidence": 0.55,
                "observed_at": observed,
                "discovery_kind": "LIVE_ONCHAIN_CANDIDATE",
            }
        return list(latest.values())

    def _priority_independence(self, wallet: str, peers: list[str]) -> float:
        actor = getattr(self.engine, "actor", None)
        if actor is None or not hasattr(actor, "independence_factor"):
            return 1.0
        try:
            return float(actor.independence_factor(wallet, peers))
        except Exception:
            return 1.0

    def _priority_select(
        self,
        qualification_by_wallet: dict[str, dict[str, Any]],
        *,
        limit: int,
        now: datetime,
    ) -> list[dict[str, Any]]:
        rows = [dict(x) for x in qualification_by_wallet.values()]
        if limit <= 0 or not rows:
            return []

        if not bool(self.settings.external_discovery.wallet_priority_enabled):
            ranked_rows = [x for x in rows if x.get("rank") is not None]
            emerging_rows = [x for x in rows if x.get("rank") is None]
            ranked_rows.sort(key=lambda x: (int(x.get("rank") or 10**9), -(float(x.get("monthly_pnl") or 0.0))))
            emerging_rows.sort(
                key=lambda x: (
                    -(x.get("observed_at").timestamp() if isinstance(x.get("observed_at"), datetime) else 0.0),
                    str(x.get("wallet_address") or ""),
                )
            )
            top_fraction = max(0.0, min(1.0, float(self.settings.external_discovery.top_wallet_backfill_fraction)))
            if ranked_rows and emerging_rows and limit > 1:
                top_slots = max(1, min(limit - 1, int(round(limit * top_fraction))))
                selected = ranked_rows[:top_slots] + emerging_rows[: limit - top_slots]
            else:
                selected = (ranked_rows + emerging_rows)[:limit]
            return selected[:limit]

        # Stage 1 is deliberately cheap and keeps the expensive 7d/30d wallet analytics
        # bounded even if the live registry grows into the thousands.
        prelim = []
        for row in rows:
            wallet = str(row.get("wallet_address") or "").strip()
            if not wallet:
                continue
            context = self.engine.discovery.wallet_context(wallet, now)
            scored = self.wallet_priority.score(
                row,
                smart_metrics=None,
                discovery_context=context,
                independence_score=1.0,
                now=now,
            )
            row.update(scored)
            prelim.append(row)
        prelim.sort(key=lambda x: float(x.get("wallet_discovery_priority_score") or 0.0), reverse=True)

        pool_size = max(
            limit,
            min(
                len(prelim),
                max(limit, int(self.settings.external_discovery.wallet_priority_candidate_pool)),
            ),
        )
        pool = prelim[:pool_size]
        peer_wallets = [str(x.get("wallet_address") or "") for x in pool if x.get("wallet_address")]

        fully_scored = []
        store = getattr(self.engine, "store", None)
        smart_engine = getattr(self.engine, "smart", None)
        for row in pool:
            wallet = str(row.get("wallet_address") or "").strip()
            context = self.engine.discovery.wallet_context(wallet, now)
            smart_metrics = {}
            if store is not None and smart_engine is not None:
                try:
                    smart_metrics = smart_engine.emerging_wallet_metrics(wallet, now, store)
                except Exception:
                    smart_metrics = {}
            independence = self._priority_independence(wallet, peer_wallets)
            scored = self.wallet_priority.score(
                row,
                smart_metrics=smart_metrics,
                discovery_context=context,
                independence_score=independence,
                now=now,
            )
            row.update(scored)
            row["priority_smart_metrics"] = {
                "smart_capital_30d_score": smart_metrics.get("smart_capital_30d_score"),
                "emerging_smart_wallet_score": smart_metrics.get("emerging_smart_wallet_score"),
                "data_quality_score": smart_metrics.get("data_quality_score"),
                "sample_size_30d": smart_metrics.get("sample_size_30d"),
            }
            fully_scored.append(row)

        fully_scored.sort(
            key=lambda x: (
                float(x.get("wallet_discovery_priority_score") or 0.0),
                -(int(x.get("rank") or 10**9)),
            ),
            reverse=True,
        )
        return fully_scored[:limit]

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

        limit = max(0, int(max_wallets or self.settings.external_discovery.max_wallets_per_refresh))

        # Qualification is broader than the external leaderboard: keep top-ranked wallets
        # while reserving part of the Helius budget for newly observed on-chain wallets
        # that may become EMERGING_SMART_WALLET candidates.
        qualification_by_wallet: dict[str, dict[str, Any]] = {}
        for row in self._seed_rows_from_registry():
            wallet = str(row.get("wallet_address") or "").strip()
            if wallet:
                qualification_by_wallet[wallet] = dict(row)
        for row in rows:
            wallet = str(row.get("wallet_address") or "").strip()
            if wallet:
                merged = dict(qualification_by_wallet.get(wallet) or {})
                merged.update(row)
                merged["discovery_kind"] = "TOP_LEADERBOARD" if row.get("rank") is not None else merged.get("discovery_kind")
                qualification_by_wallet[wallet] = merged

        now = datetime.now(timezone.utc)
        min_age = max(60.0, float(self.settings.helius_history.refresh_seconds))
        skipped_recent = 0

        # Remove recently-qualified wallets before ranking so they do not consume one of
        # the scarce Helius slots and leave budget unused.
        eligible: dict[str, dict[str, Any]] = {}
        for wallet, row in qualification_by_wallet.items():
            previous = self._last_backfill.get(wallet)
            if previous is not None and (now - previous).total_seconds() < min_age:
                skipped_recent += 1
                continue
            eligible[wallet] = row

        selected = self._priority_select(eligible, limit=limit, now=now)

        backfills = []
        if self.settings.helius_history.enabled and self.settings.helius_api_key and selected:
            client = HeliusWalletHistoryClient(self.settings.helius_api_key)
            service = WalletResearchBackfillService(client, repository=self.engine.repository, min_funding_sol=self.settings.helius_history.min_funding_sol)
            due_wallets = [
                str(row.get("wallet_address") or "").strip()
                for row in selected
                if str(row.get("wallet_address") or "").strip()
            ]

            semaphore = asyncio.Semaphore(max(1, int(self.settings.helius_history.max_concurrency)))

            async def fetch_one(wallet: str):
                async with semaphore:
                    try:
                        bundle = await service.fetch_wallet_bundle(
                            wallet,
                            limit=self.settings.helius_history.page_limit,
                            max_pages=self.settings.helius_history.max_pages,
                        )
                        return wallet, bundle, None
                    except Exception as exc:
                        return wallet, None, {
                            "wallet": wallet,
                            "error": type(exc).__name__,
                            "message": str(exc)[:200],
                        }

            if due_wallets:
                fetched = list(await asyncio.gather(*(fetch_one(w) for w in due_wallets)))
                bundles = [bundle for _, bundle, error in fetched if bundle is not None and error is None]

                # Mutate the shared Actor Graph in one globally chronological pass. Network
                # fetches remain concurrent, but wallet request completion order cannot
                # create false co-buy sequence structure.
                actor_events = sorted(
                    (event for bundle in bundles for event in bundle.events),
                    key=lambda event: (event.timestamp, event.event_id),
                )
                self.engine.actor.observe_historical_batch(actor_events)

                funding_links = sorted(
                    (link for bundle in bundles for link in bundle.funding_links),
                    key=lambda link: (link.timestamp, link.wallet, link.funder),
                )
                for link in funding_links:
                    self.engine.actor.observe_funding_link(
                        link.wallet, link.funder, link.timestamp, link.confidence
                    )

                for wallet, bundle, error in fetched:
                    if error is not None:
                        backfills.append(error)
                        continue
                    result = service.apply_bundle(
                        bundle,
                        self.engine.store,
                        self.engine.actor,
                        apply_actor_events=False,
                        apply_funding=False,
                    )
                    result_payload = asdict(result)
                    backfills.append(result_payload)
                    self._seen_wallets.add(wallet)
                    self._last_backfill[wallet] = now
                    repository = getattr(self.engine, "repository", None)
                    if repository is not None and hasattr(repository, "record_wallet_backfill_status"):
                        repository.record_wallet_backfill_status(wallet, now, result_payload)

        self._last_sync = datetime.now(timezone.utc)
        status = "OK" if qualification_by_wallet else "WAITING_DISCOVERY_SOURCE"
        self._last_result = {
            "status": status,
            "discovery_source": discovery_source,
            "observed_at": observed_at,
            "leaderboard_rows": len(rows),
            "qualification_candidates": len(qualification_by_wallet),
            "selected_for_backfill": len(selected),
            "selected_top_wallets": sum(1 for x in selected if x.get("rank") is not None),
            "selected_emerging_wallets": sum(1 for x in selected if x.get("rank") is None),
            "wallet_priority_enabled": bool(self.settings.external_discovery.wallet_priority_enabled),
            "selected_wallet_priorities": [
                {
                    "wallet_address": x.get("wallet_address"),
                    "rank": x.get("rank"),
                    "discovery_kind": x.get("discovery_kind"),
                    "priority_score": x.get("wallet_discovery_priority_score"),
                    "priority_components": x.get("wallet_discovery_priority_components"),
                }
                for x in selected
            ],
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
