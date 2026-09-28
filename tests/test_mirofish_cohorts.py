from datetime import datetime, timezone

from runner_genesis.config import MiroFishConfig
from runner_genesis.engines.mirofish import MiroFishRolloutEngine


def test_mirofish_reads_wallet_breadth_and_cohort_risk():
    cfg = MiroFishConfig(
        enabled=True,
        num_rollouts=16,
        require_min_data_quality=0.0,
        rollout_timeout_ms=1000,
    )
    engine = MiroFishRolloutEngine(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    base = {
        "data_quality_score": 0.9,
        "weighted_smart_capital_consensus": 0.7,
        "accumulation_score": 0.7,
        "runner_persistence": 0.6,
        "launch_integrity_score": 0.8,
        "coordinated_dump_risk": 0.1,
        "effective_wallet_count": 3.5,
        "top_trader_independence_ratio": 0.9,
    }
    independent = engine.rollouts(
        "M1", now,
        {**base, "independence_ratio": 0.9, "cohort_concentration": 0.2, "same_funder_concentration": 0.1},
    )
    coordinated = engine.rollouts(
        "M2", now,
        {**base, "independence_ratio": 0.25, "cohort_concentration": 0.9, "same_funder_concentration": 0.85},
    )
    assert independent["mirofish_independent_breadth"] > coordinated["mirofish_independent_breadth"]
    assert independent["mirofish_coordinated_cohort_risk"] < coordinated["mirofish_coordinated_cohort_risk"]
