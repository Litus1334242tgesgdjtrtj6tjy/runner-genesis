from __future__ import annotations

from datetime import datetime, timezone
from math import exp, log1p, tanh
from typing import Any


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class WalletDiscoveryPriorityEngine:
    """Prioritize scarce historical-wallet research budget.

    This score decides which wallets deserve Helius backfill first. It is NOT a trade
    signal and external leaderboard rank never bypasses on-chain qualification.
    """

    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def _weights(self) -> dict[str, float]:
        raw = {
            "rank": float(self.cfg.wallet_priority_rank_weight),
            "rank_momentum": float(self.cfg.wallet_priority_rank_momentum_weight),
            "smart_30d": float(self.cfg.wallet_priority_smart_30d_weight),
            "emerging": float(self.cfg.wallet_priority_emerging_weight),
            "recent_activity": float(self.cfg.wallet_priority_recent_activity_weight),
            "independence": float(self.cfg.wallet_priority_independence_weight),
            "cohort_quality": float(self.cfg.wallet_priority_cohort_weight),
            "data_gap": float(self.cfg.wallet_priority_data_gap_weight),
            "source_confidence": float(self.cfg.wallet_priority_source_confidence_weight),
        }
        total = sum(max(0.0, x) for x in raw.values())
        if total <= 0:
            return {k: 0.0 for k in raw}
        return {k: max(0.0, v) / total for k, v in raw.items()}

    @staticmethod
    def _rank_score(rank: Any) -> float:
        try:
            r = max(1.0, float(rank))
        except (TypeError, ValueError):
            return 0.0
        # Rank 1 = 1.0, then decays smoothly without giving a huge discontinuity.
        return _clip(1.0 / (1.0 + log1p(r - 1.0)))

    @staticmethod
    def _rank_momentum(context: dict[str, Any]) -> float:
        velocity = max(0.0, float(context.get("pump_rank_velocity") or 0.0))
        acceleration = max(0.0, float(context.get("pump_rank_acceleration") or 0.0))
        return _clip(0.65 * tanh(velocity / 5.0) + 0.35 * tanh(acceleration / 10.0))

    def _recent_activity(self, observed_at: Any, now: datetime) -> float:
        if not isinstance(observed_at, datetime):
            return 0.0
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        age = (now - observed_at).total_seconds()
        if age < 0:
            return 0.0
        half_life = max(1.0, float(self.cfg.wallet_priority_activity_half_life_seconds))
        return _clip(exp(-age / half_life))

    def score(
        self,
        row: dict[str, Any],
        *,
        smart_metrics: dict[str, Any] | None,
        discovery_context: dict[str, Any] | None,
        independence_score: float,
        now: datetime,
        cohort_quality: float = 0.0,
    ) -> dict[str, Any]:
        smart = smart_metrics or {}
        discovery = discovery_context or {}
        # If discovery_context explicitly contains pump_rank, it is the point-in-time
        # current rank after freshness checks. Never revive a stale/future rank from the
        # raw registry row.
        rank = discovery.get("pump_rank") if "pump_rank" in discovery else row.get("rank")
        rank_score = self._rank_score(rank)
        momentum = self._rank_momentum(discovery)
        smart_30d = _clip(float(smart.get("smart_capital_30d_score") or 0.0))
        emerging = _clip(float(smart.get("emerging_smart_wallet_score") or 0.0))
        recent = self._recent_activity(row.get("observed_at"), now)
        independence = _clip(independence_score)
        cohort = _clip(cohort_quality)
        data_quality = _clip(float(smart.get("data_quality_score") or 0.0))
        data_gap = 1.0 - data_quality
        source_confidence = _clip(float(row.get("source_confidence") or 0.0))

        components = {
            "rank": rank_score,
            "rank_momentum": momentum,
            "smart_30d": smart_30d,
            "emerging": emerging,
            "recent_activity": recent,
            "independence": independence,
            "cohort_quality": cohort,
            "data_gap": data_gap,
            "source_confidence": source_confidence,
        }
        weights = self._weights()
        priority = _clip(sum(weights[k] * components[k] for k in components))
        return {
            "wallet_address": str(row.get("wallet_address") or ""),
            "wallet_discovery_priority_score": priority,
            "wallet_discovery_priority_components": components,
            "wallet_discovery_priority_weights": weights,
            "priority_reason": "RESEARCH_BUDGET_ONLY",
        }
