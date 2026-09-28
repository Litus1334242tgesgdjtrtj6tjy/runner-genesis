from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


@dataclass(frozen=True)
class FormationSample:
    timestamp: datetime
    consensus: float
    accumulation: float
    effective_wallets: float
    top_wave: float
    price: float | None


class EarlySmartCapitalFormationEngine:
    """Experimental point-in-time challenger for early Smart Capital formation.

    It looks for *growth* in independent Smart Capital before price has already run far.
    The output is research context only: it does not submit trades and does not bypass
    Smart Capital confirmation or the Risk Governor.
    """

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.history: dict[str, deque[FormationSample]] = defaultdict(deque)

    @staticmethod
    def _value(features: dict[str, Any], key: str) -> float:
        try:
            return float(features.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def observe_and_features(
        self,
        mint: str,
        now: datetime,
        features: dict[str, Any],
        price: float | None,
    ) -> dict[str, Any]:
        if not self.cfg.enabled:
            return {
                "early_formation_status": "DISABLED",
                "early_formation_score": 0.0,
            }

        p = float(price) if price is not None and float(price) > 0 else None
        sample = FormationSample(
            timestamp=now,
            consensus=_clip(self._value(features, "weighted_smart_capital_consensus")),
            accumulation=_clip(self._value(features, "accumulation_score")),
            effective_wallets=max(0.0, self._value(features, "effective_wallet_count")),
            top_wave=_clip(self._value(features, "top_trader_wave_score")),
            price=p,
        )
        series = self.history[mint]

        if series and now < series[-1].timestamp:
            return {
                "early_formation_status": "OUT_OF_ORDER_IGNORED",
                "early_formation_score": 0.0,
            }

        series.append(sample)
        cutoff = now - timedelta(seconds=max(1.0, float(self.cfg.history_seconds)))
        while len(series) > 1 and series[0].timestamp < cutoff:
            series.popleft()

        if len(series) < 2:
            return {
                "early_formation_status": "WARMUP",
                "early_formation_score": 0.0,
                "early_formation_elapsed_seconds": 0.0,
            }

        target = now - timedelta(seconds=max(1.0, float(self.cfg.lookback_seconds)))
        baseline = None
        for row in reversed(series):
            if row.timestamp <= target:
                baseline = row
                break
        if baseline is None:
            baseline = series[0]

        elapsed = max(0.0, (now - baseline.timestamp).total_seconds())
        if elapsed < max(1.0, float(self.cfg.min_elapsed_seconds)):
            return {
                "early_formation_status": "WARMUP",
                "early_formation_score": 0.0,
                "early_formation_elapsed_seconds": elapsed,
            }

        consensus_delta = sample.consensus - baseline.consensus
        accumulation_delta = sample.accumulation - baseline.accumulation
        wallet_delta = sample.effective_wallets - baseline.effective_wallets
        top_wave_delta = sample.top_wave - baseline.top_wave

        normalized_wallet_growth = _clip(max(0.0, wallet_delta) / 3.0)
        smart_growth = _clip(
            0.36 * max(0.0, consensus_delta)
            + 0.30 * max(0.0, accumulation_delta)
            + 0.20 * normalized_wallet_growth
            + 0.14 * max(0.0, top_wave_delta)
        )

        price_return = None
        if sample.price is not None and baseline.price is not None and baseline.price > 0:
            price_return = sample.price / baseline.price - 1.0

        max_runup = max(0.05, float(self.cfg.max_price_runup_for_headroom))
        positive_runup = max(0.0, float(price_return or 0.0))
        entry_headroom = _clip(1.0 - positive_runup / max_runup)

        independence = _clip(self._value(features, "independence_ratio"))
        integrity = _clip(self._value(features, "launch_integrity_score") or 0.5)
        manipulation = _clip(self._value(features, "manipulation_risk"))
        market_pressure = max(-1.0, min(1.0, self._value(features, "net_buy_pressure_60s")))
        market_confirmation = _clip(0.5 + 0.5 * market_pressure)

        divergence = _clip(smart_growth - 0.75 * positive_runup)
        score = _clip(
            smart_growth
            * entry_headroom
            * (0.55 + 0.25 * independence + 0.20 * integrity)
            * (0.75 + 0.25 * market_confirmation)
            * (1.0 - 0.60 * manipulation)
        )

        if score >= float(self.cfg.forming_threshold):
            status = "FORMING"
        elif score >= float(self.cfg.watch_threshold):
            status = "WATCH"
        else:
            status = "QUIET"

        return {
            "early_formation_status": status,
            "early_formation_score": score,
            "early_formation_smart_growth": smart_growth,
            "early_formation_divergence": divergence,
            "early_formation_entry_headroom": entry_headroom,
            "early_formation_price_return": price_return,
            "early_formation_consensus_delta": consensus_delta,
            "early_formation_accumulation_delta": accumulation_delta,
            "early_formation_effective_wallet_delta": wallet_delta,
            "early_formation_top_wave_delta": top_wave_delta,
            "early_formation_elapsed_seconds": elapsed,
        }
