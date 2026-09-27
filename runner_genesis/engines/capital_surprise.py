from __future__ import annotations
import math
import numpy as np
from dataclasses import dataclass, asdict
from datetime import datetime
from ..state_store import MarketStateStore
from ..domain.events import MarketEvent

@dataclass
class CapitalSurpriseResult:
    absolute_size: float
    relative_size: float
    capital_percentile: float
    robust_zscore: float
    capital_surprise: float
    wallet_conviction: float
    entry_size_vs_historical: float
    history_n: int

    def as_features(self) -> dict[str, float]:
        return {k: float(v) for k,v in asdict(self).items()}

class CapitalSurpriseEngine:
    def __init__(self, min_history: int = 5, z_cap: float = 8.0) -> None:
        self.min_history = min_history
        self.z_cap = z_cap

    def compute(self, event: MarketEvent, store: MarketStateStore) -> CapitalSurpriseResult:
        size = float(event.usd_value or 0.0)
        if not event.wallet:
            return CapitalSurpriseResult(size, 1.0, 0.5, 0.0, 0.0, 0.0, 1.0, 0)
        w = store.wallet(event.wallet)
        # Current event has not yet been applied when this function is called by orchestrator.
        hist = [b[1] for b in w.buys if b[0] < event.timestamp and b[1] > 0]
        n = len(hist)
        if n == 0:
            return CapitalSurpriseResult(size, 1.0, 0.5, 0.0, 0.15 if size > 0 else 0.0, 0.15 if size > 0 else 0.0, 1.0, 0)
        x = np.log1p(np.asarray(hist, dtype=float))
        cur = math.log1p(max(size, 0.0))
        med = float(np.median(x))
        mad = float(np.median(np.abs(x-med)))
        robust_z = 0.67448975 * (cur-med) / max(mad, 1e-8)
        robust_z = float(np.clip(robust_z, -self.z_cap, self.z_cap))
        raw = np.asarray(hist, dtype=float)
        med_raw = float(np.median(raw))
        relative = size / max(med_raw, 1e-9)
        percentile = float((np.sum(raw <= size) + 0.5) / (n + 1.0))
        # Bounded 0..1; low-sample histories get shrinkage toward neutral.
        surprise_raw = 1.0 / (1.0 + math.exp(-0.75 * max(0.0, robust_z)))
        shrink = min(1.0, n / max(self.min_history, 1))
        surprise = 0.5 + (surprise_raw - 0.5) * shrink
        surprise = max(0.0, min(1.0, surprise))
        conviction = max(0.0, min(1.0, 0.55*surprise + 0.45*percentile))
        return CapitalSurpriseResult(size, relative, percentile, robust_z, surprise, conviction, relative, n)
