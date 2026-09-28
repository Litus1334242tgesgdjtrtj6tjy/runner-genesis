from datetime import datetime, timedelta, timezone

from runner_genesis.config import MiroFishConfig
from runner_genesis.engines.mirofish import MiroFishRolloutEngine


def _features():
    return {
        "data_quality_score": 0.9,
        "weighted_smart_capital_consensus": 0.7,
        "accumulation_score": 0.7,
        "top_trader_wave_score": 0.5,
        "fomo_score": 0.2,
        "smart_capital_retention": 0.6,
        "net_buy_pressure_60s": 0.4,
        "launch_integrity_score": 0.8,
        "coordinated_dump_risk": 0.1,
        "effective_wallet_count": 3.0,
        "independence_ratio": 0.9,
        "top_trader_independence_ratio": 0.9,
    }


def test_paper_mode_reuses_stable_recent_mirofish_rollout():
    cfg = MiroFishConfig(
        enabled=True,
        num_rollouts=16,
        require_min_data_quality=0.0,
        rollout_timeout_ms=1000,
        min_rerun_seconds=20,
        material_change_threshold=0.08,
    )
    engine = MiroFishRolloutEngine(cfg, deterministic=False)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    first = engine.rollouts("M", t0, _features())
    second = engine.rollouts("M", t0 + timedelta(seconds=5), _features())

    assert first["mirofish_status"] == "SIMULATION"
    assert first["mirofish_cached"] is False
    assert second["mirofish_status"] == "SIMULATION"
    assert second["mirofish_cached"] is True
    assert second["mirofish_cache_age_seconds"] == 5.0


def test_material_feature_change_forces_new_rollout():
    cfg = MiroFishConfig(
        enabled=True,
        num_rollouts=16,
        require_min_data_quality=0.0,
        rollout_timeout_ms=1000,
        min_rerun_seconds=20,
        material_change_threshold=0.05,
    )
    engine = MiroFishRolloutEngine(cfg, deterministic=False)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.rollouts("M", t0, _features())

    changed = _features()
    changed["weighted_smart_capital_consensus"] = 0.9
    second = engine.rollouts("M", t0 + timedelta(seconds=5), changed)

    assert second["mirofish_status"] == "SIMULATION"
    assert second["mirofish_cached"] is False


def test_backtest_mode_ignores_wall_clock_timeout_and_runs_exact_count(monkeypatch):
    cfg = MiroFishConfig(
        enabled=True,
        num_rollouts=24,
        require_min_data_quality=0.0,
        rollout_timeout_ms=1,
    )
    engine = MiroFishRolloutEngine(cfg, deterministic=True)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # If wall-clock time leaked into deterministic research this would truncate after 8.
    monkeypatch.setattr("runner_genesis.engines.mirofish.time.perf_counter", lambda: 10**9)
    out = engine.rollouts("M", t0, _features())

    assert out["mirofish_status"] == "SIMULATION"
    assert out["mirofish_rollouts"] == 24.0
    assert out["mirofish_deterministic"] is True
    assert out["mirofish_cached"] is False
