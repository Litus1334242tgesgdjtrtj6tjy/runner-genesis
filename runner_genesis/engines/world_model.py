from __future__ import annotations
from pathlib import Path
import joblib
import numpy as np


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


class RunnerWorldModel:
    def __init__(self, path: str | None = None, enabled: bool = True):
        self.enabled = enabled
        self.model = None
        self.model_status = 'DISABLED' if not enabled else 'UNTRAINED'
        if enabled and path and Path(path).exists():
            self.model = joblib.load(path)
            self.model_status = 'TRAINED'

    def predict(self, f: dict) -> dict[str, float | str]:
        if not self.enabled:
            return {'world_model_status': 'DISABLED'}
        if self.model is not None:
            if isinstance(self.model, dict) and 'models' in self.model:
                order = self.model.get('feature_order', [])
                models = self.model['models']
            elif isinstance(self.model, dict):
                order = []
                models = self.model
            else:
                return {'world_model_status': 'INVALID_MODEL'}
            X = np.array([[float(f.get(k, 0) or 0) for k in order]]) if order else None
            out: dict[str, float | str] = {'world_model_status': 'TRAINED'}
            if X is not None:
                for name, m in models.items():
                    if hasattr(m, 'predict_proba'):
                        out[name] = float(m.predict_proba(X)[0, 1])
            return out

        # Heuristic state indicators are deliberately called scores, not probabilities.
        base = float(f.get('weighted_smart_capital_consensus', f.get('smart_money_consensus', 0)) or 0)
        cascade = _clip(float(f.get('runner_cascade_r', 0) or 0) / 2)
        cluster = _clip(float(f.get('cluster_density', 0) or 0))
        q = _clip(float(f.get('wallet_quality', 0) or 0))
        risk = _clip(float(f.get('token_risk', 0.5) if f.get('token_risk') is not None else 0.5))
        return {
            'world_model_status': 'UNTRAINED',
            'world_new_elite_score': _clip(0.15 + 0.35 * base + 0.20 * cluster + 0.20 * q - 0.15 * risk),
            'world_cohort_formation_score': _clip(0.10 + 0.40 * cluster + 0.25 * base + 0.15 * cascade),
            'world_smart_wave_score': _clip(0.10 + 0.40 * base + 0.30 * cascade + 0.20 * max(0.0, float(f.get('capital_surprise', 0) or 0))),
            'world_cascade_continuation_score': _clip(0.15 + 0.65 * cascade - 0.20 * risk),
        }
