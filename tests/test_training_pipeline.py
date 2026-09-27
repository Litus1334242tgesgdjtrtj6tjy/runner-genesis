from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

from runner_genesis.config import Settings
from runner_genesis.engines.genesis import FEATURE_ORDER, RunnerGenesisModel
from runner_genesis.training import (
    ExecutableLabelConfig,
    TARGETS,
    _future_labels,
    train_genesis_from_dataset,
    walk_forward_evaluate,
)


def test_future_labels_use_delayed_executable_entry_and_future_only():
    settings = Settings()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observations = [
        {"timestamp": t0 + timedelta(seconds=30), "price_usd": 0.5, "liquidity_usd": 100_000},
        {"timestamp": t0 + timedelta(seconds=60), "price_usd": 1.0, "liquidity_usd": 100_000},
        {"timestamp": t0 + timedelta(minutes=10), "price_usd": 2.2, "liquidity_usd": 100_000},
        {"timestamp": t0 + timedelta(minutes=20), "price_usd": 3.2, "liquidity_usd": 100_000},
        {"timestamp": t0 + timedelta(minutes=50), "price_usd": 5.5, "liquidity_usd": 100_000},
    ]
    labels = _future_labels(
        observations,
        t0,
        settings.execution,
        ExecutableLabelConfig(entry_delay_seconds=60, default_position_eur=10),
    )
    assert labels is not None
    assert labels["label_entry_time"] == t0 + timedelta(seconds=60)
    assert labels["label_entry_price"] == 1.0
    assert labels["y_x2_15m"] == 1
    assert labels["y_x3_30m"] == 1
    assert labels["y_x5_60m"] == 1


def test_chronological_training_writes_loadable_calibrated_artifact(tmp_path):
    n = 120
    times = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
    rows = []
    target_columns = sorted(set(TARGETS.values()))
    for i in range(n):
        positive = int(i % 2 == 0)
        row = {
            "decision_time": times[i],
            "token_mint": f"M{i}",
            "action_at_t": "WATCH",
            "model_version_at_t": "test",
        }
        for j, feature in enumerate(FEATURE_ORDER):
            row[feature] = (1.0 if positive else -1.0) + 0.01 * j + 0.001 * i
        for target in target_columns:
            row[target] = positive
        rows.append(row)

    dataset = tmp_path / "training.csv"
    model_path = tmp_path / "genesis_model.joblib"
    pd.DataFrame(rows).to_csv(dataset, index=False)

    report = train_genesis_from_dataset(dataset, model_path, min_rows=100)
    assert model_path.exists()
    assert "genesis_prob" in report["metrics"]
    assert report["split"]["train_rows"] > report["split"]["validation_rows"]

    model = RunnerGenesisModel(str(model_path))
    assert model.model_status == "TRAINED"
    features = {k: 1.0 for k in FEATURE_ORDER}
    out = model.predict(features)
    assert out["genesis_prob"] is not None
    assert 0.0 <= out["genesis_prob"] <= 1.0

    walk = walk_forward_evaluate(dataset, min_train_rows=80, folds=3)
    assert walk["aggregate"]["folds_scored"] >= 2
    assert 0.0 <= walk["aggregate"]["brier"] <= 1.0
