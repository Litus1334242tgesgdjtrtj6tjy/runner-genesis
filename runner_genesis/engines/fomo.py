from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FomoObservation:
    timestamp: datetime
    source: str
    token_mint: str
    confidence: float = 1.0
    weight: float = 1.0

class FomoDiscoveryEngine:
    """Optional context engine. With no configured observations it returns neutral/unknown-safe values."""
    def __init__(self, enabled: bool = False, max_age_seconds: float = 900.0) -> None:
        self.enabled = enabled
        self.max_age_seconds = max_age_seconds
        self.observations: list[FomoObservation] = []

    def observe(self, obs: FomoObservation) -> None:
        if self.enabled:
            self.observations.append(obs)

    def features(self, token_mint: str, as_of: datetime) -> dict[str, float | bool]:
        if not self.enabled:
            return {"fomo_enabled": False, "fomo_signal_present": False, "fomo_score": 0.0, "fomo_source_count": 0.0}
        cutoff = as_of.timestamp() - self.max_age_seconds
        xs = [o for o in self.observations if o.token_mint == token_mint and o.timestamp.timestamp() >= cutoff and o.timestamp <= as_of]
        sources = {o.source for o in xs}
        score = min(1.0, sum(max(0.0, o.confidence * o.weight) for o in xs) / 5.0)
        return {"fomo_enabled": True, "fomo_signal_present": bool(xs), "fomo_score": score, "fomo_source_count": float(len(sources))}
