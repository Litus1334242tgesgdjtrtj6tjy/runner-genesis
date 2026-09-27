from __future__ import annotations
import math


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


class RunnerPersistenceEngine:
    def compute(self, f: dict) -> dict[str, float | str]:
        retention = float(f.get('smart_capital_retention', f.get('runner_holder_retention', 0)) or 0)
        consensus = float(f.get('weighted_smart_capital_consensus', f.get('smart_money_consensus', 0)) or 0)
        accum = float(f.get('accumulation_score', 0) or 0)
        market = float(f.get('net_buy_pressure_60s', 0) or 0)
        cascade = float(f.get('runner_cascade_r', 0) or 0)
        risk = float(f.get('token_risk', 0.5) if f.get('token_risk') is not None else 0.5)
        divergence = max(0.0, float(f.get('capital_divergence', 0) or 0))
        launch = float(f.get('launch_integrity_score', 0.5) or 0.5)
        smart_distribution = float(f.get('smart_distribution_score', 0) or 0)
        fomo_persistence = float(f.get('fomo_persistence', 0) or 0)
        mirofish_p = float(f.get('mirofish_persistence_frequency', 0) or 0)
        mirofish_d = float(f.get('mirofish_distribution_frequency', 0) or 0)

        x = (
            1.55 * retention
            + 1.00 * consensus
            + 0.55 * accum
            + 0.40 * max(0.0, market)
            + 0.22 * cascade
            + 0.28 * launch
            + 0.15 * fomo_persistence
            + 0.20 * mirofish_p
            - 1.10 * risk
            - 0.95 * divergence
            - 1.05 * smart_distribution
            - 0.20 * mirofish_d
            - 0.75
        )
        p = 1 / (1 + math.exp(-max(-20, min(20, x))))
        dist = _clip(0.48 * (1 - p) + 0.36 * smart_distribution + 0.20 * divergence + 0.16 * mirofish_d)
        collapse = _clip(0.60 * dist + 0.25 * risk + 0.15 * (1 - launch))
        if p > 0.82:
            state = 'EXPANSION'
        elif p > 0.68:
            state = 'CONFIRMED_RUNNER'
        elif p > 0.55:
            state = 'EARLY_RUNNER'
        elif dist > 0.75:
            state = 'DISTRIBUTION'
        elif p < 0.22:
            state = 'DEAD'
        else:
            state = 'DISCOVERY'
        return {
            'runner_persistence': p,
            'persistence_score': p,
            'distribution_score': dist,
            'collapse_risk_score': collapse,
            'runner_state': state,
        }
