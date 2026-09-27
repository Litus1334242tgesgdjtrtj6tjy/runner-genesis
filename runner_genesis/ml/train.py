from __future__ import annotations
from pathlib import Path
import argparse, json, joblib
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from ..engines.genesis import FEATURE_ORDER

LABELS = ['genesis_label', 'x2_60m', 'x5_60m', 'x10_60m']


def train(input_path: str, out_path: str, time_col: str = 'decision_time'):
    p = Path(input_path)
    df = pd.read_parquet(p) if p.suffix == '.parquet' else pd.read_csv(p)
    df = df.sort_values(time_col).reset_index(drop=True)
    missing = [x for x in FEATURE_ORDER if x not in df.columns]
    if missing:
        raise ValueError(f'missing point-in-time feature columns: {missing}')
    n = len(df)
    if n < 60:
        raise ValueError('at least 60 chronological rows are required for a meaningful train/validation/test split')
    a = int(n * 0.70); b = int(n * 0.85)
    train_df = df.iloc[:a]; val = df.iloc[a:b]; test = df.iloc[b:]
    models = {}; metrics = {}
    for label in [x for x in LABELS if x in df.columns]:
        Xtr = train_df[FEATURE_ORDER].fillna(0); ytr = train_df[label].astype(int)
        Xv = val[FEATURE_ORDER].fillna(0); yv = val[label].astype(int)
        Xt = test[FEATURE_ORDER].fillna(0); yt = test[label].astype(int)
        base = HistGradientBoostingClassifier(max_depth=5, learning_rate=0.05, max_iter=250, l2_regularization=1.0, random_state=42)
        base.fit(Xtr, ytr)
        cal = CalibratedClassifierCV(base, method='isotonic', cv='prefit') if len(np.unique(yv)) > 1 else base
        if cal is not base:
            cal.fit(Xv, yv)
        m = cal
        models[label.replace('genesis_label', 'genesis_prob')] = m
        pr = m.predict_proba(Xt)[:, 1]
        metrics[label] = {
            'pr_auc': float(average_precision_score(yt, pr)) if len(np.unique(yt)) > 1 else None,
            'roc_auc': float(roc_auc_score(yt, pr)) if len(np.unique(yt)) > 1 else None,
            'brier': float(brier_score_loss(yt, pr)),
        }
    payload = {
        'model_version': f'genesis-trained-{datetime.now(timezone.utc).date().isoformat()}',
        'feature_order': FEATURE_ORDER,
        'models': models,
        'trained_until': str(train_df[time_col].iloc[-1]),
        'validated_until': str(val[time_col].iloc[-1]),
        'test_start': str(test[time_col].iloc[0]),
    }
    joblib.dump(payload, out_path)
    Path(out_path).with_suffix('.metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    return metrics


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('input'); ap.add_argument('output')
    args = ap.parse_args(); print(json.dumps(train(args.input, args.output), indent=2))
