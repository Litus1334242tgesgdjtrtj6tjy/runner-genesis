from __future__ import annotations
from datetime import datetime
import hashlib
import math
import time
import numpy as np


class MiroFishRolloutEngine:
    """Local MiroFish-style multi-agent scenario simulator.

    This is deliberately an experimental, self-contained stochastic simulator. It does
    not claim to know the future and does not call an external MiroFish service.
    Outputs are simulation frequencies, not calibrated probabilities.
    """

    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def _rng(self, mint: str, decision_time: datetime) -> np.random.Generator:
        key = f"{self.cfg.random_seed}|{mint}|{decision_time.isoformat()}"
        seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")
        return np.random.default_rng(seed)

    def rollouts(self, mint: str, decision_time: datetime, f: dict) -> dict[str, float | str]:
        if not self.cfg.enabled:
            return {"mirofish_status": "DISABLED"}
        dq = float(f.get("data_quality_score", 0.0) or 0.0)
        if dq < float(self.cfg.require_min_data_quality):
            return {"mirofish_status": "WAITING_DATA", "mirofish_data_quality": dq}

        consensus = float(f.get("weighted_smart_capital_consensus", f.get("smart_money_consensus", 0.0)) or 0.0)
        accum = float(f.get("accumulation_score", 0.0) or 0.0)
        top_wave = float(f.get("top_trader_wave_score", 0.0) or 0.0)
        fomo = float(f.get("fomo_score", 0.0) or 0.0)
        if not (
            consensus >= float(self.cfg.trigger_min_consensus)
            or accum >= float(self.cfg.trigger_min_accumulation)
            or top_wave >= float(self.cfg.trigger_min_top_trader_wave)
            or fomo >= float(self.cfg.trigger_min_fomo)
        ):
            return {
                "mirofish_status": "NOT_TRIGGERED",
                "mirofish_data_quality": dq,
                "mirofish_trigger_consensus": consensus,
                "mirofish_trigger_accumulation": accum,
                "mirofish_trigger_top_trader_wave": top_wave,
                "mirofish_trigger_fomo": fomo,
            }

        rng = self._rng(mint, decision_time)
        n = max(8, int(self.cfg.num_rollouts))
        steps = max(3, min(30, int(self.cfg.horizon_seconds // 30) or 3))
        deadline = time.perf_counter() + max(float(self.cfg.rollout_timeout_ms), 1.0) / 1000.0

        persistence = float(f.get("smart_capital_retention", f.get("runner_holder_retention", 0.0)) or 0.0)
        market = max(-1.0, min(1.0, float(f.get("net_buy_pressure_60s", 0.0) or 0.0)))
        integrity = float(f.get("launch_integrity_score", 0.5) or 0.5)
        dump = float(f.get("coordinated_dump_risk", 0.0) or 0.0)
        fomo = float(f.get("fomo_score", 0.0) or 0.0)
        world_prior = float(f.get("world_smart_wave_score", 0.0) or 0.0) if self.cfg.use_world_model_prior else 0.0
        effective_wallets = max(0.0, float(f.get("effective_wallet_count", 0.0) or 0.0))
        independence = max(0.0, min(1.0, float(f.get("independence_ratio", 0.0) or 0.0)))
        cohort_concentration = max(0.0, min(1.0, float(f.get("cohort_concentration", 0.0) or 0.0)))
        same_funder = max(0.0, min(1.0, float(f.get("same_funder_concentration", 0.0) or 0.0)))
        top_independence = max(0.0, min(1.0, float(f.get("top_trader_independence_ratio", 0.0) or 0.0)))
        independent_breadth = min(1.0, effective_wallets / 4.0) * max(independence, top_independence)
        coordinated_risk = max(cohort_concentration * (1.0 - independence), same_funder)

        persist_hits = 0
        distribution_hits = 0
        collapse_hits = 0
        elite_hits = 0
        cohort_hits = 0
        returns: list[float] = []
        actual = 0

        for _ in range(n):
            if time.perf_counter() > deadline and actual >= 8:
                break
            actual += 1
            capital = 0.47 * consensus + 0.27 * accum + 0.10 * world_prior + 0.16 * independent_breadth
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
                    0.08
                    + 0.46 * dump
                    + 0.20 * distribution
                    + 0.24 * coordinated_risk
                    - 0.22 * holder
                    - 0.12 * capital
                    - 0.08 * independent_breadth,
                )
                if rng.random() < min(0.80, sell_drive):
                    distribution = min(1.0, distribution + rng.uniform(0.04, 0.18))
                    capital = max(0.0, capital - rng.uniform(0.02, 0.12))
                else:
                    distribution = max(0.0, distribution - rng.uniform(0.00, 0.04))
                liquidity = max(0.0, min(1.0, liquidity + rng.normal(0.006 * (capital - distribution), 0.025)))
                holder = max(0.0, min(1.0, holder + 0.04 * (capital - distribution) + rng.normal(0.0, 0.025)))
                step_ret = 0.055 * capital + 0.035 * holder + 0.02 * market - 0.07 * distribution - 0.05 * (1.0 - liquidity)
                ret += step_ret + rng.normal(0.0, 0.035)
            returns.append(ret)
            if holder >= 0.58 and distribution < 0.52:
                persist_hits += 1
            if distribution >= 0.62:
                distribution_hits += 1
            if liquidity < 0.20 or distribution > 0.84:
                collapse_hits += 1
            if elite_arrived:
                elite_hits += 1
            if cohort_formed:
                cohort_hits += 1

        if not actual:
            return {"mirofish_status": "TIMEOUT"}
        arr = np.asarray(returns, dtype=float)
        return {
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
        }
