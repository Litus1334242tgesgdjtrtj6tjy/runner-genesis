from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True)
class StrategyBenchmarkSpec:
    code: str
    description: str
    gate: Callable[[pd.Series, Any], bool]


def _v(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if pd.isna(value):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _known(row: pd.Series, key: str) -> float | None:
    value = row.get(key)
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def strategy_specs(settings) -> tuple[StrategyBenchmarkSpec, ...]:
    sc = settings.smart_capital
    trader = settings.trader
    risk = settings.risk
    early = settings.early_formation

    weighted = lambda r: (
        _v(r, "weighted_smart_capital_consensus") >= float(sc.min_consensus)
        and _v(r, "effective_wallet_count") >= float(sc.min_effective_wallets)
    )
    weighted_accum = lambda r: (
        weighted(r)
        and _v(r, "accumulation_score") >= float(sc.min_accumulation)
    )

    def entry_distance_gate(r: pd.Series) -> bool:
        distance = _known(r, "entry_distance_price")
        return bool(
            weighted_accum(r)
            and distance is not None
            and distance <= float(sc.max_entry_distance_price)
        )

    return (
        StrategyBenchmarkSpec(
            "A_FIRST_WALLET_COPY",
            "First observed active Smart-Capital wallet; naive copy baseline.",
            lambda r, _s: _v(r, "qualified_wallet_count") >= 1.0,
        ),
        StrategyBenchmarkSpec(
            "B_TOP_PUMP_WALLET",
            "At least one current point-in-time Pump top-wallet is active.",
            lambda r, _s: _v(r, "top_trader_count") >= 1.0,
        ),
        StrategyBenchmarkSpec(
            "C_UNWEIGHTED_CONSENSUS",
            "At least two raw active Smart-Capital wallets; no quality weighting.",
            lambda r, _s: _v(r, "qualified_wallet_count") >= 2.0,
        ),
        StrategyBenchmarkSpec(
            "D_WEIGHTED_CONSENSUS",
            "Weighted Smart-Capital consensus plus effective independent breadth.",
            lambda r, _s: weighted(r),
        ),
        StrategyBenchmarkSpec(
            "E_PLUS_ACCUMULATION",
            "Weighted consensus plus accumulation confirmation.",
            lambda r, _s: weighted_accum(r),
        ),
        StrategyBenchmarkSpec(
            "F_PLUS_ENTRY_DISTANCE",
            "Weighted consensus + accumulation + point-in-time entry-distance timing.",
            lambda r, _s: entry_distance_gate(r),
        ),
        StrategyBenchmarkSpec(
            "G_FULL",
            "Current full entry gate: confirmed Smart Capital, timing, fusion, edge and sellability.",
            lambda r, _s: (
                _v(r, "signal_validity_is_valid") >= 1.0
                and _v(r, "entry_validity_is_valid") >= 1.0
                and _v(r, "fusion_risk_veto") < 0.5
                and _v(r, "fusion_research_score") >= float(trader.min_genesis_to_watch)
                and _v(r, "expected_executable_edge", -1.0) >= float(trader.min_entry_edge)
                and _v(r, "sellability_score") >= float(risk.min_sellability_score)
            ),
        ),
        StrategyBenchmarkSpec(
            "H_EARLY_FORMATION_CHALLENGER",
            "Experimental early-formation gate before full Smart-Capital confirmation.",
            lambda r, _s: (
                _v(r, "early_formation_score") >= float(early.forming_threshold)
                and _v(r, "early_formation_entry_headroom") >= 0.40
                and _v(r, "effective_wallet_count") >= 1.0
                and _v(r, "sellability_score") >= float(risk.min_sellability_score)
                and _v(r, "manipulation_risk") <= float(risk.max_manipulation_risk)
                and _v(r, "fusion_risk_veto") < 0.5
                and _v(r, "entry_too_late") < 0.5
            ),
        ),
    )


def _read_dataset(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    required = {"decision_time", "token_mint", "y_executable_runner", "mfe_net_return_60m"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"strategy benchmark dataset missing columns: {', '.join(missing)}")
    df = df.copy()
    df["decision_time"] = pd.to_datetime(df["decision_time"], utc=True)
    return df.sort_values(["decision_time", "token_mint"]).reset_index(drop=True)


def _first_signals(df: pd.DataFrame, spec: StrategyBenchmarkSpec, settings) -> pd.DataFrame:
    selected = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        mint = str(row["token_mint"])
        if mint in seen:
            continue
        if spec.gate(row, settings):
            selected.append(row)
            seen.add(mint)
    return pd.DataFrame(selected, columns=df.columns)


def _median_or_none(values) -> float | None:
    xs = [float(x) for x in values if x is not None and not pd.isna(x)]
    return float(median(xs)) if xs else None


def _mean_or_none(values) -> float | None:
    xs = [float(x) for x in values if x is not None and not pd.isna(x)]
    return float(sum(xs) / len(xs)) if xs else None


def _variant_metrics(selected: pd.DataFrame, df: pd.DataFrame) -> dict[str, Any]:
    positive_tokens = set(
        str(x)
        for x in df.loc[df["y_executable_runner"].astype(int) == 1, "token_mint"].unique()
    )
    if selected.empty:
        return {
            "signals": 0,
            "precision_executable_runner": None,
            "runner_token_recall_at_signal": 0.0 if positive_tokens else None,
            "positive_executable_mfe_rate": None,
            "mean_executable_mfe_60m": None,
            "median_executable_mfe_60m": None,
            "x2_60m_rate": None,
            "x3_60m_rate": None,
            "x5_60m_rate": None,
            "x10_60m_rate": None,
            "median_entry_distance_price": None,
            "median_early_formation_score": None,
        }

    y = selected["y_executable_runner"].astype(int)
    selected_positive_tokens = set(
        str(x)
        for x in selected.loc[y == 1, "token_mint"].unique()
    )
    mfe = pd.to_numeric(selected["mfe_net_return_60m"], errors="coerce")
    metrics = {
        "signals": int(len(selected)),
        "precision_executable_runner": float(y.mean()),
        "runner_token_recall_at_signal": (
            len(selected_positive_tokens) / len(positive_tokens)
            if positive_tokens else None
        ),
        "positive_executable_mfe_rate": float((mfe > 0).mean()) if mfe.notna().any() else None,
        "mean_executable_mfe_60m": float(mfe.mean()) if mfe.notna().any() else None,
        "median_executable_mfe_60m": float(mfe.median()) if mfe.notna().any() else None,
        "median_entry_distance_price": _median_or_none(selected.get("entry_distance_price", [])),
        "median_early_formation_score": _median_or_none(selected.get("early_formation_score", [])),
    }
    for label, key in (
        ("y_x2_60m", "x2_60m_rate"),
        ("y_x3_60m", "x3_60m_rate"),
        ("y_x5_60m", "x5_60m_rate"),
        ("y_x10_60m", "x10_60m_rate"),
    ):
        metrics[key] = (
            float(pd.to_numeric(selected[label], errors="coerce").mean())
            if label in selected.columns else None
        )
    return metrics


def benchmark_entry_strategies(
    dataset_path: str | Path,
    settings,
    specs: tuple[StrategyBenchmarkSpec, ...] | None = None,
) -> dict[str, Any]:
    """Compare A-G entry gates plus the experimental early-formation challenger.

    This is an ENTRY benchmark, not a realized-PnL backtest. Future executable MFE labels
    are used only as outcomes. Each strategy gets at most one first signal per token,
    preventing high-frequency event rows from inflating apparent precision.
    """
    df = _read_dataset(dataset_path)
    specs = specs or strategy_specs(settings)
    results: dict[str, Any] = {}
    first_by_variant: dict[str, pd.DataFrame] = {}

    for spec in specs:
        selected = _first_signals(df, spec, settings)
        first_by_variant[spec.code] = selected
        results[spec.code] = {
            "description": spec.description,
            **_variant_metrics(selected, df),
        }

    comparison: dict[str, Any] = {}
    early = first_by_variant.get("H_EARLY_FORMATION_CHALLENGER")
    full = first_by_variant.get("G_FULL")
    if early is not None and full is not None and not early.empty and not full.empty:
        e_times = {
            str(r.token_mint): r.decision_time
            for r in early.itertuples(index=False)
        }
        f_times = {
            str(r.token_mint): r.decision_time
            for r in full.itertuples(index=False)
        }
        common = sorted(set(e_times).intersection(f_times))
        leads = [
            (f_times[m] - e_times[m]).total_seconds()
            for m in common
        ]
        comparison["EARLY_FORMATION_VS_FULL"] = {
            "common_signaled_tokens": len(common),
            "median_early_lead_seconds": _median_or_none(leads),
            "mean_early_lead_seconds": _mean_or_none(leads),
            "early_before_full_fraction": (
                sum(x > 0 for x in leads) / len(leads) if leads else None
            ),
        }

    return {
        "benchmark_type": "POINT_IN_TIME_ENTRY_QUALITY",
        "realized_pnl_claim": False,
        "dataset_rows": int(len(df)),
        "unique_tokens": int(df["token_mint"].nunique()),
        "variants": results,
        "comparisons": comparison,
        "note": (
            "MFE-based outcomes measure entry quality and runner capture opportunity. "
            "Use the executable PAPER backtester for realized exit/PnL comparisons."
        ),
    }
