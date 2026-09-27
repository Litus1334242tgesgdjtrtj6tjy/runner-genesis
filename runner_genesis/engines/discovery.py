from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import exp
from typing import Any


@dataclass(frozen=True)
class LeaderboardSnapshot:
    wallet_address: str
    observed_at: datetime
    source: str = "PUMP_OFFICIAL"
    username: str | None = None
    rank: int | None = None
    monthly_pnl: float | None = None
    source_window: str | None = "1M"
    source_confidence: float = 1.0


@dataclass
class DiscoveryWallet:
    wallet_address: str
    source: str
    username: str | None = None
    source_rank: int | None = None
    source_window: str | None = None
    source_url_or_identifier: str | None = None
    first_seen: datetime | None = None
    last_verified: datetime | None = None
    mapping_confidence: float = 1.0


class PumpDiscoveryEngine:
    """Point-in-time registry for Pump/KOL/community discovery.

    Discovery is not an endorsement. Wallet quality must be verified on-chain by the
    rest of the system before a wallet can materially affect trading decisions.
    """

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.snapshots: list[LeaderboardSnapshot] = []
        self.wallet_sources: dict[str, list[DiscoveryWallet]] = defaultdict(list)
        self._last_rank: dict[tuple[str, str], tuple[datetime, int | None, float | None]] = {}
        self._velocity: dict[tuple[str, str], float] = {}
        self._acceleration: dict[tuple[str, str], float] = {}

    def ingest_leaderboard(self, rows: list[dict[str, Any]], observed_at: datetime | None = None, source: str = "PUMP_OFFICIAL") -> int:
        if not self.cfg.enabled or not self.cfg.top_traders_enabled:
            return 0
        at = observed_at or datetime.now(timezone.utc)
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        n = 0
        for row in rows:
            wallet = str(row.get("wallet_address") or row.get("wallet") or "").strip()
            if not wallet:
                continue
            rank = row.get("rank")
            rank = int(rank) if rank is not None else None
            pnl = row.get("monthly_pnl")
            pnl = float(pnl) if pnl is not None else None
            snap = LeaderboardSnapshot(
                wallet_address=wallet,
                observed_at=at,
                source=source,
                username=row.get("username"),
                rank=rank,
                monthly_pnl=pnl,
                source_window=str(row.get("source_window") or "1M"),
                source_confidence=float(row.get("source_confidence", 1.0)),
            )
            self.snapshots.append(snap)
            key = (source, wallet)
            prev = self._last_rank.get(key)
            if prev and rank is not None and prev[1] is not None:
                dt = max((at - prev[0]).total_seconds(), 1.0)
                velocity = (float(prev[1]) - float(rank)) / dt * 3600.0  # positive == improving rank/hour
                old_v = self._velocity.get(key, 0.0)
                self._velocity[key] = velocity
                self._acceleration[key] = (velocity - old_v) / dt * 3600.0
            self._last_rank[key] = (at, rank, pnl)
            self.register_wallet({
                "wallet_address": wallet,
                "source": source,
                "username": row.get("username"),
                "source_rank": rank,
                "source_window": row.get("source_window") or "1M",
                "mapping_confidence": row.get("mapping_confidence", 1.0),
                "observed_at": at,
            })
            n += 1
        self.snapshots.sort(key=lambda x: x.observed_at)
        return n

    def register_wallet(self, row: dict[str, Any]) -> None:
        wallet = str(row.get("wallet_address") or row.get("wallet") or "").strip()
        if not wallet:
            return
        at = row.get("observed_at") or datetime.now(timezone.utc)
        if isinstance(at, str):
            at = datetime.fromisoformat(at.replace("Z", "+00:00"))
        rec = DiscoveryWallet(
            wallet_address=wallet,
            source=str(row.get("source") or "COMMUNITY_DISCOVERY"),
            username=row.get("username"),
            source_rank=int(row["source_rank"]) if row.get("source_rank") is not None else None,
            source_window=row.get("source_window"),
            source_url_or_identifier=row.get("source_url_or_identifier"),
            first_seen=at,
            last_verified=at,
            mapping_confidence=max(0.0, min(1.0, float(row.get("mapping_confidence", 1.0)))),
        )
        existing = self.wallet_sources[wallet]
        for old in existing:
            if old.source == rec.source and old.username == rec.username:
                old.last_verified = at
                old.source_rank = rec.source_rank
                old.mapping_confidence = rec.mapping_confidence
                return
        existing.append(rec)

    def wallet_context(self, wallet: str, as_of: datetime) -> dict[str, float | str | None]:
        rows = [x for x in self.wallet_sources.get(wallet, []) if x.first_seen and x.first_seen <= as_of]
        if not rows:
            return {
                "discovery_source_count": 0.0,
                "pump_top_trader_present": 0.0,
                "kol_present": 0.0,
                "pump_rank": None,
                "pump_rank_velocity": 0.0,
                "pump_rank_acceleration": 0.0,
            }
        pump = [x for x in rows if x.source in {"PUMP_OFFICIAL", "PUMPFUN_TOP_TRADER"}]
        kol = [x for x in rows if "KOL" in x.source]
        latest_pump = max(pump, key=lambda x: x.last_verified or x.first_seen) if pump else None
        source = latest_pump.source if latest_pump else "PUMP_OFFICIAL"
        key = (source, wallet)
        return {
            "discovery_source_count": float(len({x.source for x in rows})),
            "pump_top_trader_present": 1.0 if pump else 0.0,
            "kol_present": 1.0 if kol else 0.0,
            "pump_rank": float(latest_pump.source_rank) if latest_pump and latest_pump.source_rank is not None else None,
            "pump_rank_velocity": float(self._velocity.get(key, 0.0)),
            "pump_rank_acceleration": float(self._acceleration.get(key, 0.0)),
        }

    def token_wave_features(self, wallets: list[str], as_of: datetime, actor=None, events: list[Any] | None = None) -> dict[str, float]:
        if not wallets:
            return {
                "top_trader_present": 0.0,
                "top_trader_count": 0.0,
                "top_trader_effective_count": 0.0,
                "top_trader_independence_ratio": 0.0,
                "kol_count": 0.0,
                "kol_effective_count": 0.0,
                "new_top_traders_30s": 0.0,
                "new_top_traders_60s": 0.0,
                "top_trader_wave_score": 0.0,
                "kol_wave_score": 0.0,
            }
        top_wallets: list[str] = []
        kol_wallets: list[str] = []
        vel = []
        for w in set(wallets):
            ctx = self.wallet_context(w, as_of)
            if float(ctx.get("pump_top_trader_present") or 0) > 0:
                top_wallets.append(w)
            if float(ctx.get("kol_present") or 0) > 0:
                kol_wallets.append(w)
            vel.append(max(0.0, float(ctx.get("pump_rank_velocity") or 0.0)))

        top_count = len(top_wallets)
        kol_count = len(kol_wallets)
        top_eff = float(actor.effective_wallet_count(top_wallets)) if actor is not None and top_wallets else float(top_count)
        kol_eff = float(actor.effective_wallet_count(kol_wallets)) if actor is not None and kol_wallets else float(kol_count)
        top_ind = top_eff / top_count if top_count else 0.0

        new30: set[str] = set()
        new60: set[str] = set()
        if events:
            top_set = set(top_wallets)
            for ev in events:
                wallet = getattr(ev, "wallet", None)
                ts = getattr(ev, "timestamp", None)
                et = getattr(ev, "event_type", None)
                if wallet not in top_set or ts is None:
                    continue
                # Any explicit BUY-like event in the trailing window counts once per wallet.
                etv = getattr(et, "value", str(et))
                if etv not in {"BUY", "RUNNER_HOLDER_ENTRY", "RUNNER_HOLDER_ADD", "SMART_WALLET_NEW_ENTRY", "SMART_WALLET_ADD"}:
                    continue
                age = (as_of - ts).total_seconds()
                if 0 <= age <= 60:
                    new60.add(wallet)
                    if age <= 30:
                        new30.add(wallet)

        breadth = min(1.0, top_eff / 4.0)
        k_breadth = min(1.0, kol_eff / 3.0)
        speed = min(1.0, sum(vel) / max(len(vel), 1) / 10.0)
        arrival = min(1.0, len(new60) / 3.0)
        return {
            "top_trader_present": 1.0 if top_count else 0.0,
            "top_trader_count": float(top_count),
            "top_trader_effective_count": top_eff,
            "top_trader_independence_ratio": top_ind,
            "kol_count": float(kol_count),
            "kol_effective_count": kol_eff,
            "new_top_traders_30s": float(len(new30)),
            "new_top_traders_60s": float(len(new60)),
            "top_trader_wave_score": max(0.0, min(1.0, 0.55 * breadth + 0.25 * arrival + 0.20 * speed)),
            "kol_wave_score": max(0.0, min(1.0, 0.75 * k_breadth + 0.25 * top_ind)),
        }

    def latest_snapshots(self, limit: int = 100) -> list[dict[str, Any]]:
        return [asdict(x) for x in self.snapshots[-limit:]]
