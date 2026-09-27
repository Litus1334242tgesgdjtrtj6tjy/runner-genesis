from datetime import datetime, timedelta, timezone

import pandas as pd

from runner_genesis.config import Settings
from runner_genesis.strategy_benchmarks import benchmark_entry_strategies


def _row(t, mint, runner, mfe, **kwargs):
    row = {
        "decision_time": t,
        "token_mint": mint,
        "y_executable_runner": int(runner),
        "mfe_net_return_60m": mfe,
        "y_x2_60m": int(mfe >= 1.0),
        "y_x3_60m": int(mfe >= 2.0),
        "y_x5_60m": int(mfe >= 4.0),
        "y_x10_60m": int(mfe >= 9.0),
        "qualified_wallet_count": 0.0,
        "top_trader_count": 0.0,
        "weighted_smart_capital_consensus": 0.0,
        "accumulation_score": 0.0,
        "effective_wallet_count": 0.0,
        "entry_distance_price": None,
        "signal_validity_is_valid": 0.0,
        "entry_validity_is_valid": 0.0,
        "fusion_risk_veto": 0.0,
        "fusion_research_score": 0.0,
        "expected_executable_edge": -1.0,
        "sellability_score": 0.9,
        "manipulation_risk": 0.05,
        "early_formation_score": 0.0,
        "early_formation_entry_headroom": 1.0,
    }
    row.update(kwargs)
    return row


def test_a_to_g_entry_benchmarks_are_first_signal_per_token(tmp_path):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        _row(t0, "RUNNER", 1, 2.2, qualified_wallet_count=1, top_trader_count=1),
        _row(
            t0 + timedelta(minutes=1), "RUNNER", 1, 1.8,
            qualified_wallet_count=3, top_trader_count=1,
            weighted_smart_capital_consensus=0.70, accumulation_score=0.65,
            effective_wallet_count=2.0, entry_distance_price=0.20,
            signal_validity_is_valid=1.0, entry_validity_is_valid=1.0,
            fusion_research_score=0.75, expected_executable_edge=0.08,
        ),
        # Later duplicate qualifying row must not become a second signal.
        _row(
            t0 + timedelta(minutes=2), "RUNNER", 1, 1.4,
            qualified_wallet_count=4, top_trader_count=2,
            weighted_smart_capital_consensus=0.80, accumulation_score=0.75,
            effective_wallet_count=3.0, entry_distance_price=0.30,
            signal_validity_is_valid=1.0, entry_validity_is_valid=1.0,
            fusion_research_score=0.80, expected_executable_edge=0.10,
        ),
        _row(t0, "LOSER", 0, 0.10, qualified_wallet_count=1),
        _row(
            t0 + timedelta(minutes=1), "LOSER", 0, 0.05,
            qualified_wallet_count=2,
            weighted_smart_capital_consensus=0.60,
            accumulation_score=0.20,
            effective_wallet_count=1.5,
            entry_distance_price=0.10,
        ),
    ]
    path = tmp_path / "bench.csv"
    pd.DataFrame(rows).to_csv(path, index=False)

    report = benchmark_entry_strategies(path, Settings())
    variants = report["variants"]

    assert variants["A_FIRST_WALLET_COPY"]["signals"] == 2
    assert variants["B_TOP_PUMP_WALLET"]["signals"] == 1
    assert variants["C_UNWEIGHTED_CONSENSUS"]["signals"] == 2
    assert variants["D_WEIGHTED_CONSENSUS"]["signals"] == 2
    assert variants["E_PLUS_ACCUMULATION"]["signals"] == 1
    assert variants["F_PLUS_ENTRY_DISTANCE"]["signals"] == 1
    assert variants["G_FULL"]["signals"] == 1
    assert variants["G_FULL"]["precision_executable_runner"] == 1.0
    assert report["realized_pnl_claim"] is False


def test_early_formation_reports_lead_time_against_full_gate(tmp_path):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        _row(
            t0, "EARLY", 1, 2.0,
            qualified_wallet_count=1, effective_wallet_count=1.2,
            early_formation_score=0.70, early_formation_entry_headroom=0.80,
            sellability_score=0.90,
        ),
        _row(
            t0 + timedelta(minutes=2), "EARLY", 1, 1.4,
            qualified_wallet_count=3, effective_wallet_count=2.0,
            weighted_smart_capital_consensus=0.70, accumulation_score=0.65,
            entry_distance_price=0.20, signal_validity_is_valid=1.0,
            entry_validity_is_valid=1.0, fusion_research_score=0.75,
            expected_executable_edge=0.08, sellability_score=0.90,
            early_formation_score=0.75, early_formation_entry_headroom=0.65,
        ),
    ]
    path = tmp_path / "early.csv"
    pd.DataFrame(rows).to_csv(path, index=False)

    report = benchmark_entry_strategies(path, Settings())
    comparison = report["comparisons"]["EARLY_FORMATION_VS_FULL"]

    assert report["variants"]["H_EARLY_FORMATION_CHALLENGER"]["signals"] == 1
    assert report["variants"]["G_FULL"]["signals"] == 1
    assert comparison["common_signaled_tokens"] == 1
    assert comparison["median_early_lead_seconds"] == 120.0
    assert comparison["early_before_full_fraction"] == 1.0


def test_entry_distance_variant_requires_known_distance(tmp_path):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = _row(
        t0, "UNKNOWN_DISTANCE", 1, 2.0,
        qualified_wallet_count=3,
        weighted_smart_capital_consensus=0.70,
        accumulation_score=0.70,
        effective_wallet_count=2.0,
        entry_distance_price=None,
    )
    path = tmp_path / "unknown.csv"
    pd.DataFrame([row]).to_csv(path, index=False)

    report = benchmark_entry_strategies(path, Settings())
    assert report["variants"]["E_PLUS_ACCUMULATION"]["signals"] == 1
    assert report["variants"]["F_PLUS_ENTRY_DISTANCE"]["signals"] == 0
