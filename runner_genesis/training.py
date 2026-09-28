from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .db import EventRow, DecisionRow
from .engines.genesis import FEATURE_ORDER
from .fees import PumpFeeSchedule


BENCHMARK_NUMERIC_FEATURES = [
    "qualified_wallet_count",
    "top_trader_count",
    "top_trader_effective_count",
    "weighted_smart_capital_consensus",
    "accumulation_score",
    "conviction_score",
    "effective_wallet_count",
    "average_wallet_quality",
    "average_strategy_match",
    "entry_distance_price",
    "entry_distance_market_cap",
    "sellability_score",
    "manipulation_risk",
    "coordinated_dump_risk",
    "fusion_research_score",
    "fusion_confidence",
    "expected_executable_edge",
    "runner_persistence",
    "distribution_score",
    "early_formation_score",
    "early_formation_entry_headroom",
    "top_trader_wave_score",
    "fomo_score",
]

TARGETS = {
    "genesis_prob": "y_executable_runner",
    "p_x2_15m": "y_x2_15m",
    "p_x2_30m": "y_x2_30m",
    "p_x2_60m": "y_x2_60m",
    "p_x3_30m": "y_x3_30m",
    "p_x3_60m": "y_x3_60m",
    "p_x5_60m": "y_x5_60m",
    "p_x10_60m": "y_x10_60m",
}


@dataclass
class ExecutableLabelConfig:
    entry_delay_seconds: float = 60.0
    entry_search_seconds: float = 120.0
    default_position_eur: float = 10.0
    minimum_executable_eur: float = 2.0
    horizons_seconds: tuple[int, ...] = (900, 1800, 3600)
    fixed_exit_tolerance_seconds: float = 120.0


class PlattCalibratedBinaryModel:
    """Serializable binary estimator with chronological validation-set calibration."""

    def __init__(self, base, calibrator=None):
        self.base = base
        self.calibrator = calibrator

    @staticmethod
    def _logit(p: np.ndarray) -> np.ndarray:
        p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p)).reshape(-1, 1)

    def predict_proba(self, X):
        raw = self.base.predict_proba(X)[:, 1]
        if self.calibrator is None:
            p = raw
        else:
            p = self.calibrator.predict_proba(self._logit(raw))[:, 1]
        return np.column_stack([1.0 - p, p])


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _numeric_features(snapshot: dict[str, Any]) -> dict[str, float | None]:
    features = snapshot.get("features") if isinstance(snapshot.get("features"), dict) else {}
    out: dict[str, float | None] = {}
    for key in dict.fromkeys([*FEATURE_ORDER, *BENCHMARK_NUMERIC_FEATURES]):
        value = features.get(key)
        if value is None:
            # Model inputs retain their historical zero-imputation semantics. Research
            # benchmark fields keep UNKNOWN as None so an absent entry-distance value
            # cannot accidentally pass a timing gate.
            out[key] = 0.0 if key in FEATURE_ORDER else None
            continue
        try:
            out[key] = float(value) if not isinstance(value, bool) else float(value)
        except (TypeError, ValueError):
            out[key] = 0.0 if key in FEATURE_ORDER else None

    out["signal_validity_is_valid"] = 1.0 if str(features.get("signal_validity")) == "VALID" else 0.0
    out["entry_validity_is_valid"] = 1.0 if str(features.get("entry_validity")) == "VALID" else 0.0
    out["entry_too_late"] = 1.0 if str(features.get("entry_validity")) == "ENTRY_TOO_LATE" else 0.0
    out["fusion_risk_veto"] = 1.0 if bool(features.get("fusion_risk_veto", False)) else 0.0
    return out


def _event_observation(row: EventRow, execution_cfg=None) -> dict[str, Any] | None:
    try:
        payload = json.loads(row.payload_json)
    except Exception:
        return None
    if not bool(payload.get("asset_match_verified", row.asset_match_verified)):
        return None
    price = payload.get("price_usd")
    liquidity = payload.get("liquidity_usd")
    try:
        price = float(price) if price is not None else None
        liquidity = float(liquidity) if liquidity is not None else None
    except (TypeError, ValueError):
        return None
    if price is None or liquidity is None or price <= 0 or liquidity <= 0:
        return None
    meta = dict(payload.get("metadata") or {})
    synthetic = SimpleNamespace(
        metadata=meta,
        events=[],
        migration_at=_aware(row.timestamp) if str(payload.get("event_type") or "") == "MIGRATION" else None,
        market_cap_usd=payload.get("market_cap_usd"),
    )
    fee_quote = PumpFeeSchedule().quote(synthetic)
    network_fee_eur = 0.0
    if execution_cfg is not None:
        try:
            sol_usd = float(meta.get("sol_usd")) if meta.get("sol_usd") is not None else None
        except (TypeError, ValueError):
            sol_usd = None
        if sol_usd and sol_usd > 0:
            lamports = (
                max(0, int(execution_cfg.network_base_fee_lamports))
                * max(1, int(execution_cfg.network_signature_count))
                + max(0, int(execution_cfg.network_priority_fee_lamports))
            )
            network_fee_eur = float(lamports) * 1e-9 * sol_usd
    return {
        "timestamp": _aware(row.timestamp),
        "price_usd": price,
        "liquidity_usd": liquidity,
        "event_id": row.event_id,
        "protocol_fee_bps": fee_quote.protocol_fee_bps,
        "fee_source": fee_quote.source,
        "network_fee_eur": network_fee_eur,
    }


def _slippage(amount: float, liquidity: float, execution_cfg) -> float:
    liquidity = max(float(liquidity), 1.0)
    return (
        float(execution_cfg.base_slippage_bps)
        + float(execution_cfg.mev_adverse_bps)
    ) / 10000.0 + float(execution_cfg.impact_coefficient) * (float(amount) / liquidity)


def _roundtrip_return(entry: dict[str, Any], exit_obs: dict[str, Any], requested_eur: float, execution_cfg, max_slippage_pct: float | None = None) -> tuple[float, float] | None:
    max_entry = float(entry["liquidity_usd"]) * float(execution_cfg.max_liquidity_fraction)
    filled = min(float(requested_eur), max_entry)
    if filled <= 0:
        return None

    entry_slip = _slippage(filled, entry["liquidity_usd"], execution_cfg)
    if max_slippage_pct is not None and entry_slip > float(max_slippage_pct):
        return None
    buy_price = float(entry["price_usd"]) * (1.0 + entry_slip)
    entry_protocol_bps = entry.get("protocol_fee_bps")
    if entry_protocol_bps is None:
        entry_protocol_bps = float(execution_cfg.base_fee_bps)
    entry_fee_rate = (float(entry_protocol_bps) + float(execution_cfg.priority_fee_bps)) / 10000.0
    entry_fee = filled * entry_fee_rate + float(entry.get("network_fee_eur") or 0.0)
    quantity = filled / max(buy_price, 1e-12)

    ref_exit_notional = quantity * float(exit_obs["price_usd"])
    max_exit = float(exit_obs["liquidity_usd"]) * float(execution_cfg.max_liquidity_fraction)
    executable_notional = min(ref_exit_notional, max_exit)
    if executable_notional <= 0:
        return None
    executable_fraction = min(1.0, executable_notional / max(ref_exit_notional, 1e-12))
    qty_exit = quantity * executable_fraction
    sell_ref = qty_exit * float(exit_obs["price_usd"])
    exit_slip = _slippage(sell_ref, exit_obs["liquidity_usd"], execution_cfg)
    if max_slippage_pct is not None and exit_slip > float(max_slippage_pct):
        return None
    sell_price = float(exit_obs["price_usd"]) * max(0.0, 1.0 - exit_slip)
    proceeds = qty_exit * sell_price
    exit_protocol_bps = exit_obs.get("protocol_fee_bps")
    if exit_protocol_bps is None:
        exit_protocol_bps = float(execution_cfg.base_fee_bps)
    exit_fee_rate = (float(exit_protocol_bps) + float(execution_cfg.priority_fee_bps)) / 10000.0
    exit_fee = proceeds * exit_fee_rate + float(exit_obs.get("network_fee_eur") or 0.0)

    # Compare like-for-like capital if only a partial exit is executable.
    allocated_entry_cost = (filled + entry_fee) * executable_fraction
    net = proceeds - exit_fee - allocated_entry_cost
    ret = net / max(allocated_entry_cost, 1e-12)
    return ret, filled * executable_fraction


def _label_horizon_fully_observed(
    decision_time: datetime,
    dataset_observed_until: datetime | None,
    label_cfg: ExecutableLabelConfig,
) -> bool:
    """Reject right-censored labels whose full future horizon was never captured."""
    if dataset_observed_until is None:
        return False
    decision_time = _aware(decision_time)
    dataset_observed_until = _aware(dataset_observed_until)
    required_until = decision_time + timedelta(seconds=max(label_cfg.horizons_seconds))
    return dataset_observed_until >= required_until


def _future_labels(
    observations: list[dict[str, Any]],
    decision_time: datetime,
    execution_cfg,
    label_cfg: ExecutableLabelConfig,
    max_slippage_pct: float | None = None,
) -> dict[str, Any] | None:
    if not observations:
        return None
    target_entry = decision_time + timedelta(seconds=float(label_cfg.entry_delay_seconds))
    latest_entry = target_entry + timedelta(seconds=float(label_cfg.entry_search_seconds))
    entry = next((x for x in observations if target_entry <= x["timestamp"] <= latest_entry), None)
    if entry is None:
        return None

    max_fill = float(entry["liquidity_usd"]) * float(execution_cfg.max_liquidity_fraction)
    if min(float(label_cfg.default_position_eur), max_fill) < float(label_cfg.minimum_executable_eur):
        return None

    result: dict[str, Any] = {
        # A label is not knowable at decision time. Keep the timestamp at which the full
        # longest horizon becomes observable so temporal splits can purge boundary rows.
        "label_available_at": decision_time + timedelta(seconds=max(label_cfg.horizons_seconds)),
        "label_entry_time": entry["timestamp"],
        "label_entry_price": entry["price_usd"],
        "label_entry_liquidity": entry["liquidity_usd"],
        "label_entry_protocol_fee_bps": entry.get("protocol_fee_bps"),
        "label_entry_fee_source": entry.get("fee_source"),
    }
    horizon_returns: dict[int, list[float]] = {}
    horizon_exec_sizes: dict[int, list[float]] = {}
    fixed_horizon_returns: dict[int, float | None] = {}
    for horizon in label_cfg.horizons_seconds:
        end = decision_time + timedelta(seconds=int(horizon))
        rows = [x for x in observations if entry["timestamp"] <= x["timestamp"] <= end]
        returns = []
        sizes = []
        for row in rows:
            rr = _roundtrip_return(entry, row, label_cfg.default_position_eur, execution_cfg, max_slippage_pct=max_slippage_pct)
            if rr is None:
                continue
            ret, executable = rr
            if executable < label_cfg.minimum_executable_eur:
                continue
            returns.append(float(ret))
            sizes.append(float(executable))
        horizon_returns[int(horizon)] = returns
        horizon_exec_sizes[int(horizon)] = sizes

        tolerance = max(0.0, float(label_cfg.fixed_exit_tolerance_seconds))
        fixed_candidates: list[tuple[datetime, float]] = []
        for row in rows:
            age_to_horizon = (end - row["timestamp"]).total_seconds()
            if age_to_horizon < 0 or age_to_horizon > tolerance:
                continue
            rr = _roundtrip_return(
                entry,
                row,
                label_cfg.default_position_eur,
                execution_cfg,
                max_slippage_pct=max_slippage_pct,
            )
            if rr is None:
                continue
            ret, executable = rr
            if executable < label_cfg.minimum_executable_eur:
                continue
            fixed_candidates.append((row["timestamp"], float(ret)))
        fixed_horizon_returns[int(horizon)] = (
            max(fixed_candidates, key=lambda x: x[0])[1]
            if fixed_candidates else None
        )

    def max_ret(h: int) -> float | None:
        xs = horizon_returns.get(h, [])
        return max(xs) if xs else None

    r15, r30, r60 = max_ret(900), max_ret(1800), max_ret(3600)
    if r60 is None:
        return None

    result.update({
        "mfe_net_return_15m": r15,
        "mfe_net_return_30m": r30,
        "mfe_net_return_60m": r60,
        "fixed_exit_net_return_15m": fixed_horizon_returns.get(900),
        "fixed_exit_net_return_30m": fixed_horizon_returns.get(1800),
        "fixed_exit_net_return_60m": fixed_horizon_returns.get(3600),
        "min_executable_eur_60m": min(horizon_exec_sizes.get(3600, []) or [0.0]),
        "sellable_observations_60m": len(horizon_returns.get(3600, [])),
        "y_executable_runner": int(r60 >= 1.0),
        "y_x2_15m": int(r15 is not None and r15 >= 1.0),
        "y_x2_30m": int(r30 is not None and r30 >= 1.0),
        "y_x2_60m": int(r60 >= 1.0),
        "y_x3_30m": int(r30 is not None and r30 >= 2.0),
        "y_x3_60m": int(r60 >= 2.0),
        "y_x5_60m": int(r60 >= 4.0),
        "y_x10_60m": int(r60 >= 9.0),
    })
    return result


def build_executable_dataset(
    database_url: str,
    settings,
    output_path: str | Path,
    label_cfg: ExecutableLabelConfig | None = None,
) -> pd.DataFrame:
    """Build future labels from persisted point-in-time decisions.

    Features come only from each DecisionSnapshot at time T. Future market observations
    are used solely for labels, never injected back into the feature vector.
    """
    label_cfg = label_cfg or ExecutableLabelConfig(
        entry_delay_seconds=float(settings.execution.execution_delay_seconds),
        default_position_eur=float(settings.trader.default_position_eur),
    )
    engine = create_engine(database_url, future=True)
    by_token: dict[str, list[dict[str, Any]]] = {}
    with Session(engine) as session:
        events = session.execute(
            select(EventRow).order_by(EventRow.timestamp.asc(), EventRow.id.asc())
        ).scalars().all()
        decisions = session.execute(
            select(DecisionRow).order_by(DecisionRow.timestamp.asc(), DecisionRow.id.asc())
        ).scalars().all()

    observed_event_times = [_aware(row.timestamp) for row in events]
    dataset_observed_until = max(observed_event_times, default=None)
    for row in events:
        obs = _event_observation(row, settings.execution)
        if obs is not None:
            by_token.setdefault(row.token_mint, []).append(obs)

    rows_out: list[dict[str, Any]] = []
    for row in decisions:
        try:
            snapshot = json.loads(row.snapshot_json)
        except Exception:
            continue
        decision_time = _aware(row.timestamp)
        available = snapshot.get("data_available_until")
        if isinstance(available, str):
            try:
                available_dt = datetime.fromisoformat(available.replace("Z", "+00:00"))
                if available_dt.tzinfo is None:
                    available_dt = available_dt.replace(tzinfo=timezone.utc)
                if available_dt > decision_time:
                    continue
            except ValueError:
                continue
        if not _label_horizon_fully_observed(
            decision_time,
            dataset_observed_until,
            label_cfg,
        ):
            # Decisions near the end of a capture are unknown, not negative.
            continue
        labels = _future_labels(
            by_token.get(row.token_mint, []),
            decision_time,
            settings.execution,
            label_cfg,
            max_slippage_pct=float(settings.risk.max_slippage_pct),
        )
        if labels is None:
            continue
        base = {
            "decision_time": decision_time,
            "token_mint": row.token_mint,
            "action_at_t": row.action,
            "model_version_at_t": row.model_version,
        }
        base.update(_numeric_features(snapshot))
        base.update(labels)
        rows_out.append(base)

    df = pd.DataFrame(rows_out)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".parquet":
        try:
            df.to_parquet(out, index=False)
        except ImportError:
            out = out.with_suffix(".csv")
            df.to_csv(out, index=False)
    else:
        df.to_csv(out, index=False)
    return df


def _with_label_availability(df: pd.DataFrame, default_horizon_seconds: int = 3600) -> pd.DataFrame:
    """Normalize the time when each future-derived label became knowable."""
    out = df.copy()
    out["decision_time"] = pd.to_datetime(out["decision_time"], utc=True)
    if "label_available_at" in out.columns:
        parsed = pd.to_datetime(out["label_available_at"], utc=True, errors="coerce")
        fallback = out["decision_time"] + pd.to_timedelta(default_horizon_seconds, unit="s")
        out["label_available_at"] = parsed.fillna(fallback)
    else:
        out["label_available_at"] = out["decision_time"] + pd.to_timedelta(default_horizon_seconds, unit="s")
    return out


def _purge_before_boundary(frame: pd.DataFrame, boundary: pd.Timestamp) -> pd.DataFrame:
    """Rows are trainable only when their labels were available before next-period start."""
    return frame.loc[frame["label_available_at"] < boundary].copy()


def _purge_token_overlap(frame: pd.DataFrame, future_frame: pd.DataFrame) -> pd.DataFrame:
    """Conservative new-token OOS guard: the same mint cannot straddle model partitions."""
    if "token_mint" not in frame.columns or "token_mint" not in future_frame.columns:
        return frame.copy()
    blocked = set(future_frame["token_mint"].dropna().astype(str))
    if not blocked:
        return frame.copy()
    return frame.loc[~frame["token_mint"].astype(str).isin(blocked)].copy()


def _token_balanced_weights(frame: pd.DataFrame) -> np.ndarray:
    """Give every token roughly equal total training mass despite different event counts."""
    if len(frame) == 0:
        return np.asarray([], dtype=float)
    if "token_mint" not in frame.columns:
        return np.ones(len(frame), dtype=float)
    tokens = frame["token_mint"].fillna("__UNKNOWN__").astype(str)
    counts = tokens.value_counts()
    weights = tokens.map(lambda x: 1.0 / max(float(counts.get(x, 1)), 1.0)).to_numpy(dtype=float)
    mean = float(weights.mean()) if len(weights) else 1.0
    return weights / max(mean, 1e-12)


def _earliest_token_metric(frame: pd.DataFrame, target: str, probabilities: np.ndarray) -> dict[str, float | None]:
    """Measure OOS classification once per token using its earliest scored decision."""
    if len(frame) == 0 or "token_mint" not in frame.columns:
        return {}
    tmp = frame[["token_mint", "decision_time", target]].copy()
    tmp["_p"] = np.asarray(probabilities, dtype=float)
    tmp = tmp.sort_values(["decision_time", "token_mint"]).drop_duplicates("token_mint", keep="first")
    metrics = _safe_metric(tmp[target].astype(int).to_numpy(), tmp["_p"].to_numpy(dtype=float))
    return {f"token_earliest_{k}": v for k, v in metrics.items()}


def _expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    if len(y) == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, max(2, int(bins)) + 1)
    error = 0.0
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if i == len(edges) - 2:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        error += (n / len(y)) * abs(float(p[mask].mean()) - float(y[mask].mean()))
    return float(error)


def _safe_metric(y: np.ndarray, p: np.ndarray) -> dict[str, float | None]:
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    pred = p >= 0.5
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)

    top_n = max(1, int(np.ceil(len(y) * 0.10))) if len(y) else 0
    precision_at_10pct = None
    if top_n:
        order = np.argsort(-p)[:top_n]
        precision_at_10pct = float(y[order].mean())

    out: dict[str, float | None] = {
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, np.column_stack([1 - p, p]), labels=[0, 1])),
        "roc_auc": None,
        "pr_auc": None,
        "precision_0_5": float(precision),
        "recall_0_5": float(recall),
        "f1_0_5": float(f1),
        "precision_at_10pct": precision_at_10pct,
        "ece_10bin": _expected_calibration_error(y, p, bins=10),
        "true_positive": float(tp),
        "false_positive": float(fp),
        "false_negative": float(fn),
        "true_negative": float(tn),
    }
    if len(np.unique(y)) >= 2:
        out["roc_auc"] = float(roc_auc_score(y, p))
        out["pr_auc"] = float(average_precision_score(y, p))
    return out


def train_genesis_from_dataset(
    dataset_path: str | Path,
    model_output: str | Path,
    *,
    min_rows: int = 100,
    group_purge_tokens: bool = True,
    token_balance: bool = True,
) -> dict[str, Any]:
    path = Path(dataset_path)
    df = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    if "decision_time" not in df:
        raise ValueError("dataset requires decision_time")
    df = _with_label_availability(df)
    df = df.sort_values("decision_time").reset_index(drop=True)
    if len(df) < int(min_rows):
        raise ValueError(f"need at least {min_rows} labeled rows, got {len(df)}")

    n = len(df)
    train_end = max(1, int(n * 0.70))
    val_end = max(train_end + 1, int(n * 0.85))
    val_end = min(val_end, n - 1)
    val_start_time = df.iloc[train_end]["decision_time"]
    test_start_time = df.iloc[val_end]["decision_time"]

    raw_train = df.iloc[:train_end]
    raw_val = df.iloc[train_end:val_end]
    test = df.iloc[val_end:].copy()
    train = _purge_before_boundary(raw_train, val_start_time)
    val = _purge_before_boundary(raw_val, test_start_time)
    temporal_train_rows = len(train)
    temporal_val_rows = len(val)
    if group_purge_tokens:
        # A mint seen in validation/test is withheld from earlier fitting partitions.
        # This is intentionally conservative for a detector whose deployment target is
        # newly launched tokens rather than later observations of already-known mints.
        train = _purge_token_overlap(train, pd.concat([val, test], ignore_index=True))
        val = _purge_token_overlap(val, test)
    if len(train) == 0 or len(val) == 0 or len(test) == 0:
        raise ValueError("purged chronological train/validation/test splits are empty")

    X_train = train.reindex(columns=FEATURE_ORDER, fill_value=0.0).fillna(0.0).astype(float).to_numpy()
    X_val = val.reindex(columns=FEATURE_ORDER, fill_value=0.0).fillna(0.0).astype(float).to_numpy()
    X_test = test.reindex(columns=FEATURE_ORDER, fill_value=0.0).fillna(0.0).astype(float).to_numpy()

    models = {}
    metrics = {}
    skipped = {}
    for output_name, target in TARGETS.items():
        if target not in df:
            skipped[output_name] = "MISSING_TARGET"
            continue
        y_train = train[target].astype(int).to_numpy()
        y_val = val[target].astype(int).to_numpy()
        y_test = test[target].astype(int).to_numpy()
        if len(np.unique(y_train)) < 2:
            skipped[output_name] = "TRAIN_SINGLE_CLASS"
            continue

        base = Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=783)),
        ])
        train_weights = _token_balanced_weights(train) if token_balance else None
        if train_weights is None:
            base.fit(X_train, y_train)
        else:
            base.fit(X_train, y_train, clf__sample_weight=train_weights)
        raw_val = np.clip(base.predict_proba(X_val)[:, 1], 1e-6, 1 - 1e-6)

        calibrator = None
        if len(np.unique(y_val)) >= 2:
            logits = np.log(raw_val / (1 - raw_val)).reshape(-1, 1)
            calibrator = LogisticRegression(max_iter=1000, random_state=783)
            val_weights = _token_balanced_weights(val) if token_balance else None
            if val_weights is None:
                calibrator.fit(logits, y_val)
            else:
                calibrator.fit(logits, y_val, sample_weight=val_weights)

        model = PlattCalibratedBinaryModel(base, calibrator)
        p_test = model.predict_proba(X_test)[:, 1]
        models[output_name] = model
        metrics[output_name] = {
            **_safe_metric(y_test, p_test),
            **_earliest_token_metric(test, target, p_test),
            "train_rows": len(train),
            "validation_rows": len(val),
            "test_rows": len(test),
            "purged_train_rows": len(raw_train) - len(train),
            "purged_validation_rows": len(raw_val) - len(val),
            "token_overlap_purged_train_rows": temporal_train_rows - len(train),
            "token_overlap_purged_validation_rows": temporal_val_rows - len(val),
            "unique_train_tokens": int(train["token_mint"].nunique()) if "token_mint" in train else None,
            "unique_validation_tokens": int(val["token_mint"].nunique()) if "token_mint" in val else None,
            "unique_test_tokens": int(test["token_mint"].nunique()) if "token_mint" in test else None,
            "train_positive_rate": float(np.mean(y_train)),
            "validation_positive_rate": float(np.mean(y_val)),
            "test_positive_rate": float(np.mean(y_test)),
            "calibrated": calibrator is not None,
        }

    if "genesis_prob" not in models:
        raise ValueError("could not train genesis_prob; training split lacks both classes")

    artifact = {
        "models": models,
        "feature_order": FEATURE_ORDER,
        "model_version": f"chronological-logit-platt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "split": {
            "train_end": str(train.iloc[-1]["decision_time"]),
            "validation_end": str(val.iloc[-1]["decision_time"]),
            "test_end": str(test.iloc[-1]["decision_time"]),
            "train_rows": len(train),
            "validation_rows": len(val),
            "test_rows": len(test),
            "raw_train_rows": len(raw_train),
            "raw_validation_rows": len(raw_val),
            "label_availability_purge": True,
            "token_group_purge": bool(group_purge_tokens),
            "token_balanced_training": bool(token_balance),
            "validation_start": str(val_start_time),
            "test_start": str(test_start_time),
        },
        "metrics": metrics,
        "skipped_targets": skipped,
        "label_semantics": {
            "entry_delay_seconds": "from dataset builder",
            "genesis_prob": "probability of executable >=2x net-return threshold within 60m label",
        },
    }
    out = Path(model_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, out)
    return {k: v for k, v in artifact.items() if k != "models"}



def walk_forward_evaluate(
    dataset_path: str | Path,
    *,
    target: str = "y_executable_runner",
    min_train_rows: int = 100,
    folds: int = 4,
    group_purge_tokens: bool = True,
    token_balance: bool = True,
) -> dict[str, Any]:
    """Expanding chronological walk-forward evaluation with in-window Platt calibration."""
    path = Path(dataset_path)
    df = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    if target not in df or "decision_time" not in df:
        raise ValueError(f"dataset requires decision_time and {target}")
    df = _with_label_availability(df)
    df = df.sort_values("decision_time").reset_index(drop=True)
    n = len(df)
    min_train_rows = max(20, int(min_train_rows))
    if n <= min_train_rows + 10:
        raise ValueError("not enough rows for walk-forward evaluation")
    folds = max(2, int(folds))
    remaining = n - min_train_rows
    block = max(1, remaining // folds)

    fold_results = []
    all_y = []
    all_p = []
    for fold in range(folds):
        test_start = min_train_rows + fold * block
        test_end = n if fold == folds - 1 else min(n, test_start + block)
        if test_start >= n or test_end <= test_start:
            continue
        test = df.iloc[test_start:test_end].copy()
        test_boundary = test.iloc[0]["decision_time"]
        raw_history = df.iloc[:test_start]
        history = _purge_before_boundary(raw_history, test_boundary)
        temporal_history_rows = len(history)
        if group_purge_tokens:
            history = _purge_token_overlap(history, test)
        calibration_rows = max(10, int(len(history) * 0.20))
        fit_end = len(history) - calibration_rows
        if fit_end < 20 or calibration_rows >= len(history):
            fold_results.append({
                "fold": fold,
                "status": "SKIP_INSUFFICIENT_PURGED_HISTORY",
                "raw_history_rows": len(raw_history),
                "eligible_history_rows": len(history),
            })
            continue
        raw_fit = history.iloc[:fit_end]
        calibration = history.iloc[fit_end:].copy()
        calibration_boundary = calibration.iloc[0]["decision_time"]
        fit = _purge_before_boundary(raw_fit, calibration_boundary)
        temporal_fit_rows = len(fit)
        if group_purge_tokens:
            fit = _purge_token_overlap(fit, calibration)
        if len(fit) < 20:
            fold_results.append({
                "fold": fold,
                "status": "SKIP_INSUFFICIENT_PURGED_FIT",
                "raw_fit_rows": len(raw_fit),
                "fit_rows": len(fit),
            })
            continue

        y_fit = fit[target].astype(int).to_numpy()
        y_cal = calibration[target].astype(int).to_numpy()
        y_test = test[target].astype(int).to_numpy()
        if len(np.unique(y_fit)) < 2:
            fold_results.append({"fold": fold, "status": "SKIP_FIT_SINGLE_CLASS"})
            continue

        X_fit = fit.reindex(columns=FEATURE_ORDER, fill_value=0.0).fillna(0.0).astype(float).to_numpy()
        X_cal = calibration.reindex(columns=FEATURE_ORDER, fill_value=0.0).fillna(0.0).astype(float).to_numpy()
        X_test = test.reindex(columns=FEATURE_ORDER, fill_value=0.0).fillna(0.0).astype(float).to_numpy()

        base = Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=783 + fold)),
        ])
        fit_weights = _token_balanced_weights(fit) if token_balance else None
        if fit_weights is None:
            base.fit(X_fit, y_fit)
        else:
            base.fit(X_fit, y_fit, clf__sample_weight=fit_weights)

        calibrator = None
        raw_cal = np.clip(base.predict_proba(X_cal)[:, 1], 1e-6, 1 - 1e-6)
        if len(np.unique(y_cal)) >= 2:
            logits = np.log(raw_cal / (1 - raw_cal)).reshape(-1, 1)
            calibrator = LogisticRegression(max_iter=1000, random_state=1783 + fold)
            cal_weights = _token_balanced_weights(calibration) if token_balance else None
            if cal_weights is None:
                calibrator.fit(logits, y_cal)
            else:
                calibrator.fit(logits, y_cal, sample_weight=cal_weights)
        model = PlattCalibratedBinaryModel(base, calibrator)
        p_test = model.predict_proba(X_test)[:, 1]
        metrics = _safe_metric(y_test, p_test)
        metrics.update(_earliest_token_metric(test, target, p_test))
        fold_results.append({
            "fold": fold,
            "status": "OK",
            "fit_rows": len(fit),
            "calibration_rows": len(calibration),
            "test_rows": len(test),
            "purged_history_rows": len(raw_history) - len(history),
            "purged_fit_rows": len(raw_fit) - len(fit),
            "token_overlap_purged_history_rows": temporal_history_rows - len(history),
            "token_overlap_purged_fit_rows": temporal_fit_rows - len(fit),
            "unique_test_tokens": int(test["token_mint"].nunique()) if "token_mint" in test else None,
            "train_end": str(history.iloc[-1]["decision_time"]),
            "test_start": str(test.iloc[0]["decision_time"]),
            "test_end": str(test.iloc[-1]["decision_time"]),
            "test_positive_rate": float(np.mean(y_test)),
            "calibrated": calibrator is not None,
            **metrics,
        })
        all_y.extend(y_test.tolist())
        all_p.extend(p_test.tolist())

    ok = [x for x in fold_results if x.get("status") == "OK"]
    if not ok:
        raise ValueError("no valid walk-forward folds")
    aggregate = _safe_metric(np.asarray(all_y, dtype=int), np.asarray(all_p, dtype=float))
    aggregate.update({
        "rows_scored": len(all_y),
        "folds_scored": len(ok),
        "positive_rate": float(np.mean(all_y)) if all_y else None,
    })
    return {
        "target": target,
        "feature_order": FEATURE_ORDER,
        "token_group_purge": bool(group_purge_tokens),
        "token_balanced_training": bool(token_balance),
        "folds": fold_results,
        "aggregate": aggregate,
    }
