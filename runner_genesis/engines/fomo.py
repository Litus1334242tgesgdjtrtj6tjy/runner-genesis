from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class FomoObservation:
    token_mint: str
    timestamp: datetime
    source: str
    kind: str = "MENTION"
    confidence: float = 1.0
    actor_key: str | None = None
    metadata: dict[str, Any] | None = None


class FomoEngine:
    """Optional attention/discovery context. It is never an unconditional entry trigger."""

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.by_token: dict[str, list[FomoObservation]] = defaultdict(list)

    def ingest(self, row: dict[str, Any]) -> FomoObservation:
        ts = row.get("timestamp") or datetime.now(timezone.utc)
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        obs = FomoObservation(
            token_mint=str(row["token_mint"]),
            timestamp=ts,
            source=str(row.get("source") or "UNKNOWN"),
            kind=str(row.get("kind") or "MENTION"),
            confidence=max(0.0, min(1.0, float(row.get("confidence", 1.0)))),
            actor_key=row.get("actor_key"),
            metadata=row.get("metadata") or {},
        )
        self.by_token[obs.token_mint].append(obs)
        self.by_token[obs.token_mint].sort(key=lambda x: x.timestamp)
        return obs

    def features(self, mint: str, now: datetime) -> dict[str, float | str]:
        if not self.cfg.enabled:
            return {
                "fomo_status": "DISABLED",
                "fomo_score": 0.0,
                "fomo_source_count": 0.0,
                "fomo_independent_source_count": 0.0,
                "fomo_velocity": 0.0,
                "fomo_acceleration": 0.0,
                "fomo_persistence": 0.0,
            }
        max_age = timedelta(seconds=float(self.cfg.maximum_source_age_seconds))
        rows = [x for x in self.by_token.get(mint, []) if timedelta(0) <= now - x.timestamp <= max_age and x.confidence >= self.cfg.minimum_source_confidence]
        window = max(float(self.cfg.window_seconds), 1.0)
        recent = [x for x in rows if (now - x.timestamp).total_seconds() <= window]
        short = [x for x in rows if (now - x.timestamp).total_seconds() <= window / 3.0]
        sources = {x.source for x in recent}
        actors = {f"{x.source}:{x.actor_key or x.source}" for x in recent}
        velocity = len(recent) / window
        short_velocity = len(short) / max(window / 3.0, 1.0)
        accel = short_velocity - velocity
        confidence = sum(x.confidence for x in recent) / max(len(recent), 1)
        persistence = min(1.0, len({int((now - x.timestamp).total_seconds() // max(window / 3, 1)) for x in recent}) / 3.0)
        breadth = min(1.0, len(actors) / 5.0)
        score = max(0.0, min(1.0, 0.35 * breadth + 0.25 * min(1.0, velocity * 30.0) + 0.20 * min(1.0, max(accel, 0.0) * 20.0) + 0.20 * confidence))
        return {
            "fomo_status": "ACTIVE",
            "fomo_score": score,
            "fomo_source_count": float(len(sources)),
            "fomo_independent_source_count": float(len(actors)),
            "fomo_velocity": velocity,
            "fomo_acceleration": accel,
            "fomo_persistence": persistence,
        }

    def recent(self, mint: str, limit: int = 100) -> list[dict[str, Any]]:
        return [asdict(x) for x in self.by_token.get(mint, [])[-limit:]]
