from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from bisect import bisect_right
from collections import defaultdict

@dataclass(frozen=True)
class PumpLeaderboardSnapshot:
    wallet_address: str
    observed_at: datetime
    rank: int | None = None
    monthly_pnl: float | None = None
    username: str | None = None
    source: str = "PUMP_OFFICIAL_1M"
    confidence: float = 1.0

class PumpDiscoveryEngine:
    """Point-in-time Pump.fun discovery registry.

    It deliberately does not scrape or assume an undocumented endpoint. Adapters feed
    observed snapshots into this registry. Historical snapshots are append-only.
    """
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.by_wallet: dict[str, list[PumpLeaderboardSnapshot]] = defaultdict(list)

    def observe_snapshot(self, snap: PumpLeaderboardSnapshot) -> None:
        if not self.enabled:
            return
        arr = self.by_wallet[snap.wallet_address]
        arr.append(snap)
        arr.sort(key=lambda x: x.observed_at)

    def snapshot_as_of(self, wallet: str, as_of: datetime) -> PumpLeaderboardSnapshot | None:
        arr = self.by_wallet.get(wallet, [])
        if not arr:
            return None
        times = [x.observed_at for x in arr]
        i = bisect_right(times, as_of) - 1
        return arr[i] if i >= 0 else None

    def rank_dynamics(self, wallet: str, as_of: datetime) -> dict[str, float | None]:
        arr = [x for x in self.by_wallet.get(wallet, []) if x.observed_at <= as_of]
        if len(arr) < 2:
            cur = arr[-1] if arr else None
            return {"pump_rank": float(cur.rank) if cur and cur.rank is not None else None,"pump_rank_previous": None,"rank_velocity": None,"rank_acceleration": None}
        a, b = arr[-2], arr[-1]
        dt = max((b.observed_at - a.observed_at).total_seconds(), 1.0)
        velocity = ((a.rank - b.rank) / dt) if a.rank is not None and b.rank is not None else None
        acceleration = None
        if len(arr) >= 3 and velocity is not None:
            p = arr[-3]
            dt_prev = max((a.observed_at - p.observed_at).total_seconds(), 1.0)
            prev_v = ((p.rank - a.rank) / dt_prev) if p.rank is not None and a.rank is not None else None
            if prev_v is not None: acceleration = (velocity - prev_v) / max(dt, 1.0)
        return {"pump_rank": float(b.rank) if b.rank is not None else None,"pump_rank_previous": float(a.rank) if a.rank is not None else None,"rank_velocity": velocity,"rank_acceleration": acceleration}
