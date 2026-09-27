from datetime import datetime, timedelta, timezone

from runner_genesis.config import EarlyFormationConfig, MiroFishConfig
from runner_genesis.engines.early_formation import EarlySmartCapitalFormationEngine
from runner_genesis.engines.mirofish import MiroFishRolloutEngine


def _base(consensus=0.20, accumulation=0.20, effective=1.0, top_wave=0.10):
    return {
        "weighted_smart_capital_consensus": consensus,
        "accumulation_score": accumulation,
        "effective_wallet_count": effective,
        "top_trader_wave_score": top_wave,
        "independence_ratio": 0.90,
        "launch_integrity_score": 0.85,
        "manipulation_risk": 0.05,
        "net_buy_pressure_60s": 0.25,
    }


def test_early_formation_rewards_smart_growth_before_large_price_runup():
    cfg = EarlyFormationConfig(
        lookback_seconds=60,
        min_elapsed_seconds=20,
        max_price_runup_for_headroom=0.60,
    )
    eng = EarlySmartCapitalFormationEngine(cfg)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = eng.observe_and_features("M", t0, _base(), 1.0)
    later = eng.observe_and_features(
        "M",
        t0 + timedelta(seconds=60),
        _base(consensus=0.85, accumulation=0.80, effective=4.0, top_wave=0.75),
        1.10,
    )
    assert first["early_formation_status"] == "WARMUP"
    assert later["early_formation_score"] > 0.35
    assert later["early_formation_entry_headroom"] > 0.7
    assert later["early_formation_smart_growth"] > 0.4


def test_early_formation_penalizes_late_price_extension():
    cfg = EarlyFormationConfig(lookback_seconds=60, min_elapsed_seconds=20)
    early = EarlySmartCapitalFormationEngine(cfg)
    late = EarlySmartCapitalFormationEngine(cfg)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    start = _base()
    grown = _base(consensus=0.85, accumulation=0.80, effective=4.0, top_wave=0.75)

    early.observe_and_features("M", t0, start, 1.0)
    late.observe_and_features("M", t0, start, 1.0)
    a = early.observe_and_features("M", t0 + timedelta(seconds=60), grown, 1.10)
    b = late.observe_and_features("M", t0 + timedelta(seconds=60), grown, 1.80)

    assert a["early_formation_score"] > b["early_formation_score"]
    assert b["early_formation_entry_headroom"] == 0.0


def test_out_of_order_sample_is_ignored_without_mutating_history():
    eng = EarlySmartCapitalFormationEngine(EarlyFormationConfig(min_elapsed_seconds=1))
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    eng.observe_and_features("M", t0 + timedelta(seconds=10), _base(), 1.0)
    before = len(eng.history["M"])
    out = eng.observe_and_features("M", t0, _base(consensus=0.9), 1.0)
    assert out["early_formation_status"] == "OUT_OF_ORDER_IGNORED"
    assert len(eng.history["M"]) == before


def test_mirofish_can_be_triggered_by_early_formation_context():
    cfg = MiroFishConfig(
        enabled=True,
        num_rollouts=8,
        require_min_data_quality=0.0,
        trigger_min_consensus=0.99,
        trigger_min_accumulation=0.99,
        trigger_min_top_trader_wave=0.99,
        trigger_min_fomo=0.99,
        trigger_min_early_formation=0.40,
        rollout_timeout_ms=1000,
    )
    eng = MiroFishRolloutEngine(cfg, deterministic=True)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = eng.rollouts(
        "M",
        t0,
        {
            "data_quality_score": 0.9,
            "weighted_smart_capital_consensus": 0.2,
            "accumulation_score": 0.2,
            "top_trader_wave_score": 0.1,
            "fomo_score": 0.1,
            "early_formation_score": 0.6,
            "effective_wallet_count": 2.0,
            "independence_ratio": 0.9,
            "launch_integrity_score": 0.8,
        },
    )
    assert out["mirofish_status"] == "SIMULATION"
    assert out["mirofish_early_formation_input"] == 0.6
