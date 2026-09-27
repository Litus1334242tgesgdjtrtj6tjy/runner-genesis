from __future__ import annotations
from datetime import datetime
import hashlib
import time
import numpy as np


class MiroFishRolloutEngine:
    """Local MiroFish-style scenario simulator.

    PAPER/SHADOW may reuse a recent rollout when its driving state barely changed, keeping
    the deep path cheap during event bursts. BACKTEST/REPLAY should instantiate this engine
    with deterministic=True so every candidate executes exactly the configured rollout
    count and wall-clock speed cannot alter research results.
    """

    DRIVER_KEYS = (
        "weighted_smart_capital_consensus",
        "smart_money_consensus",
        "accumulation_score",
        "top_trader_wave_score",
        "fomo_score",
        "smart_capital_retention",
        "runner_holder_retention",
        "net_buy_pressure_60s",
        "launch_integrity_score",
        "coordinated_dump_risk",
        "world_smart_wave_score",
        "effective_wallet_count",
        "independence_ratio",
        "cohort_concentration",
        "same_funder_concentration",
        "top_trader_independence_ratio",
        "data_quality_score",
        "early_formation_score",
    )

    def __init__(self, cfg, deterministic: bool = False) -> None:
        self.cfg = cfg
        self.deterministic = bool(deterministic)
        self._cache: dict[str, tuple[datetime, tuple[float, ...], dict]] = {}

    def _rng(self, mint: str, decision_time: datetime) -> np.random.Generator:
        key = f"{self.cfg.random_seed}|{mint}|{decision_time.isoformat()}"
        seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")
        return np.random.default_rng(seed)

    @classmethod
    def _driver_signature(cls, f: dict) -> tuple[float, ...]:
        values = []
        for key in cls.DRIVER_KEYS:
            try:
                values.append(float(f.get(key, 0.0) or 0.0))
            except (TypeError, ValueError):
                values.append(0.0)
        return tuple(values)

    def _cached_if_stable(self, mint: str, decision_time: datetime, signature: tuple[float, ...]):
        if self.deterministic:
            return None
        cached = self._cache.get(mint)
        if cached is None:
            return None
        previous_time, previous_signature, previous_result = cached
        dt = (decision_time - previous_time).total_seconds()
        if dt <= 0 or dt > max(0.0, float(self.cfg.min_rerun_seconds)):
            return None
        change = max((abs(a - b) for a, b in zip(signature, previous_signature)), default=0.0)
        if change > max(0.0, float(self.cfg.material_change_threshold)):
            return None
        result = dict(previous_result)
        result["mirofish_cached"] = True
        result["mirofish_cache_age_seconds"] = max(0.0, dt)
        result["mirofish_driver_change"] = change
        return result

    def rollouts(self, mint: str, decision_time: datetime, f: dict) -> dict[str, float | str | bool]:
        if not self.cfg.enabled:
            return {"mirofish_status": "DISABLED"}
        dq = float(f.get("data_quality_score", 0.0) or 0.0)
        if dq < float(self.cfg.require_min_data_quality):
            return {"mirofish_status": "WAITING_DATA", "mirofish_data_quality": dq}

        consensus = float(f.get("weighted_smart_capital_consensus", f.get("smart_money_consensus", 0.0)) or 0.0)
        accum = float(f.get("accumulation_score", 0.0) or 0.0)
        top_wave = float(f.get("top_trader_wave_score", 0.0) or 0.0)
        fomo = float(f.get("fomo_score", 0.0) or 0.0)
        formation = float(f.get("early_formation_score", 0.0) or 0.0)
        if not (
            consensus >= float(self.cfg.trigger_min_consensus)
            or accum >= float(self.cfg.trigger_min_accumulation)
            or top_wave >= float(self.cfg.trigger_min_top_trader_wave)
            or fomo >= float(self.cfg.trigger_min_fomo)
            or formation >= float(self.cfg.trigger_min_early_formation)
        ):
            return {
                "mirofish_status": "NOT_TRIGGERED",
                "mirofish_data_quality": dq,
                "mirofish_trigger_consensus": consensus,
                "mirofish_trigger_accumulation": accum,
                "mirofish_trigger_top_trader_wave": top_wave,
                "mirofish_trigger_fomo": fomo,
                "mirofish_trigger_early_formation": formation,
            }

        signature = self._driver_signature(f)
        cached = self._cached_if_stable(mint, decision_time, signature)
        if cached is not None:
            return cached

        rng = self._rng(mint, decision_time)
        n = max(8, int(self.cfg.num_rollouts))
        steps = max(3, min(30, int(self.cfg.horizon_seconds // 30) or 3))
        deadline = None if self.deterministic else (
            time.perf_counter() + max(float(self.cfg.rollout_timeout_ms), 1.0) / 1000.0
        )

        persistence = float(f.get("smart_capital_retention", f.get("runner_holder_retention", 0.0)) or 0.0)
        market = max(-1.0, min(1.0, float(f.get("net_buy_pressure_60s", 0.0) or 0.0)))
        integrity = float(f.get("launch_integrity_score", 0.5) or 0.5)
        dump = float(f.get("coordinated_dump_risk", 0.0) or 0.0)
        world_prior = float(f.get("world_smart_wave_score", 0.0) or 0.0) if self.cfg.use_world_model_prior else 0.0
        effective_wallets = max(0.0, float(f.get("effective_wallet_count", 0.0) or 0.0))
        independence = max(0.0, min(1.0, float(f.get("independence_ratio", 0.0) or 0.0)))
        cohort_concentration = max(0.0, min(1.0, float(f.get("cohort_concentration", 0.0) or 0.0)))
        same_funder = max(0.0, min(1.0, float(f.get("same_funder_concentration", 0.0) or 0.0)))
        top_independence = max(0.0, min(1.0, float(f.get("top_trader_independence_ratio", 0.0) or 0.0)))
        independence_mix = 0.70 * independence + 0.30 * top_independence
        independent_breadth = min(1.0, effective_wallets / 4.0) * independence_mix
        coordinated_risk = max(cohort_concentration * (1.0 - independence), same_funder)

        persist_hits = distribution_hits = collapse_hits = elite_hits = cohort_hits = 0
        returns: list[float] = []
        actual = 0

        for _ in range(n):
            if deadline is not None and time.perf_counter() > deadline and actual >= 8:
                break
            actual += 1
            capital = (
                0.43 * consensus
                + 0.24 * accum
                + 0.09 * world_prior
                + 0.14 * independent_breadth
                + 0.10 * formation
            )
            holder = persistence
            liquidity = 0.45 + 0.45 * integrity
            distribution = min(1.0, dump * 0.55 + 0.25 * coordinated_risk)
            ret = 0.0
            elite_arrived = False
            cohort_formed = False
            for _step in range(steps):
                arrival_drive = (
                    0.20 * capital
                    + 0.12 * max(market, 0.0)
                    + 0.09 * fomo
                    + 0.08 * world_prior
                    + 0.11 * independent_breadth
                    + 0.10 * formation
                    - 0.10 * coordinated_risk
                )
                if rng.random() < max(0.01, min(0.65, 0.05 + arrival_drive)):
                    capital = min(1.0, capital + rng.uniform(0.03, 0.16))
                    elite_arrived = elite_arrived or rng.random() < (0.25 + 0.45 * consensus)
                if rng.random() < max(0.01, min(0.55, 0.03 + 0.28 * capital * integrity + 0.18 * independent_breadth)):
                    cohort_formed = True
                    holder = min(1.0, holder + rng.uniform(0.02, 0.12))
                sell_drive = max(
                    0.0,
                    0.08 + 0.46 * dump + 0.20 * distribution + 0.24 * coordinated_risk
                    - 0.22 * holder - 0.12 * capital - 0.08 * independent_breadth,
                )
                if rng.random() < min(0.80, sell_drive):
                    distribution = min(1.0, distribution + rng.uniform(0.04, 0.18))
                    capital = max(0.0, capital - rng.uniform(0.02, 0.12))
                else:
                    distribution = max(0.0, distribution - rng.uniform(0.00, 0.04))
                liquidity = max(0.0, min(1.0, liquidity + rng.normal(0.006 * (capital - distribution), 0.025)))
                holder = max(0.0, min(1.0, holder + 0.04 * (capital - distribution) + rng.normal(0.0, 0.025)))
                ret += 0.055 * capital + 0.035 * holder + 0.02 * market - 0.07 * distribution - 0.05 * (1.0 - liquidity) + rng.normal(0.0, 0.035)
            returns.append(ret)
            persist_hits += int(holder >= 0.58 and distribution < 0.52)
            distribution_hits += int(distribution >= 0.62)
            collapse_hits += int(liquidity < 0.20 or distribution > 0.84)
            elite_hits += int(elite_arrived)
            cohort_hits += int(cohort_formed)

        if not actual:
            return {"mirofish_status": "TIMEOUT"}
        arr = np.asarray(returns, dtype=float)
        result = {
            "mirofish_status": "SIMULATION",
            "mirofish_rollouts": float(actual),
            "mirofish_persistence_frequency": persist_hits / actual,
            "mirofish_distribution_frequency": distribution_hits / actual,
            "mirofish_collapse_frequency": collapse_hits / actual,
            "mirofish_new_elite_frequency": elite_hits / actual,
            "mirofish_cohort_formation_frequency": cohort_hits / actual,
            "mirofish_expected_return_proxy": float(arr.mean()),
            "mirofish_downside_proxy": float(np.quantile(arr, 0.10)),
            "mirofish_dispersion": float(arr.std()),
            "mirofish_data_quality": dq,
            "mirofish_independent_breadth": independent_breadth,
            "mirofish_coordinated_cohort_risk": coordinated_risk,
            "mirofish_early_formation_input": formation,
            "mirofish_cached": False,
            "mirofish_deterministic": self.deterministic,
        }
        if not self.deterministic:
            self._cache[mint] = (decision_time, signature, dict(result))
        return result
