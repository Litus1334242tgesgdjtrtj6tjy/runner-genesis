from __future__ import annotations
import math
from pathlib import Path
import joblib
import numpy as np


FEATURE_ORDER = [
    'capital_surprise', 'wallet_quality', 'pre_funding_score', 'cluster_density',
    'buyer_acceleration', 'net_buy_pressure_60s', 'token_risk', 'runner_cascade_r',
    'capital_convergence', 'flow_coherence', 'runner_holder_retention',
    'smart_money_consensus', 'jump_state_positive_mass', 'higher_order_edge_fraction',
    'fly_state_change', 'quantum_localization', 'weighted_smart_capital_consensus',
    'accumulation_score', 'conviction_score', 'effective_wallet_count',
    'launch_integrity_score', 'coordinated_dump_risk', 'sellability_score',
    'fomo_score', 'top_trader_wave_score', 'kol_wave_score',
]


class RunnerGenesisModel:
    def __init__(self, model_path: str | None = None):
        self.model = None
        self.feature_order = FEATURE_ORDER
        self.model_version = 'heuristic-baseline-v0.2'
        self.model_status = 'UNTRAINED'
        if model_path and Path(model_path).exists():
            obj = joblib.load(model_path)
            if isinstance(obj, dict) and 'models' in obj:
                self.model = obj['models']
                self.feature_order = obj.get('feature_order') or FEATURE_ORDER
                self.model_version = str(obj.get('model_version') or 'trained-joblib')
            else:
                self.model = obj
                self.model_version = getattr(obj, 'model_version', 'trained-joblib')
            self.model_status = 'TRAINED'

    def _vector(self, f):
        return np.array([[float(f.get(k, 0.0) or 0.0) for k in self.feature_order]], dtype=float)

    def heuristic_score(self, f: dict) -> float:
        risk = float(f.get('token_risk', 0.5) if f.get('token_risk') is not None else 0.5)
        launch = float(f.get('launch_integrity_score', 0.5) or 0.5)
        dump = float(f.get('coordinated_dump_risk', 0.0) or 0.0)
        x = (
            0.90 * float(f.get('capital_surprise', 0) or 0)
            + 0.65 * float(f.get('wallet_quality', 0) or 0)
            + 0.45 * float(f.get('pre_funding_score', 0) or 0)
            + 0.35 * max(0.0, float(f.get('buyer_acceleration', 0) or 0))
            + 1.10 * float(f.get('weighted_smart_capital_consensus', f.get('smart_money_consensus', 0)) or 0)
            + 0.60 * float(f.get('accumulation_score', 0) or 0)
            + 0.35 * float(f.get('conviction_score', 0) or 0)
            + 0.40 * float(f.get('runner_cascade_r', 0) or 0)
            + 0.45 * max(0.0, float(f.get('capital_convergence', 0) or 0))
            + 0.45 * launch
            - 1.05 * risk
            - 0.95 * dump
            - 2.10
        )
        return 1 / (1 + math.exp(-max(-20, min(20, x))))

    def predict(self, f: dict) -> dict[str, float | None]:
        if self.model is not None:
            if isinstance(self.model, dict):
                out: dict[str, float | None] = {}
                for label, m in self.model.items():
                    if hasattr(m, 'predict_proba'):
                        out[label] = float(m.predict_proba(self._vector(f))[0, 1])
                return out
            p = float(self.model.predict_proba(self._vector(f))[0, 1])
            return {'genesis_prob': p}
        # Transparent research score only. It is NOT exposed as a calibrated probability.
        score = self.heuristic_score(f)
        return {
            'genesis_score': score,
            'genesis_prob': None,
            'p_x2_15m': None,
            'p_x2_30m': None,
            'p_x2_60m': None,
            'p_x3_30m': None,
            'p_x3_60m': None,
            'p_x5_60m': None,
            'p_x10_60m': None,
        }
