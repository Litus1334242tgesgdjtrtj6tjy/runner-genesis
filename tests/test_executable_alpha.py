from runner_genesis.config import ExecutionConfig
from runner_genesis.engines.executable_alpha import ExecutableAlphaModel


def test_roundtrip_costs_double_one_way_friction():
    cfg = ExecutionConfig(
        base_fee_bps=35,
        priority_fee_bps=10,
        mev_adverse_bps=20,
        base_slippage_bps=35,
        impact_coefficient=0.0,
    )
    model = ExecutableAlphaModel()
    f = {
        "liquidity_usd": 100_000,
        "estimated_protocol_fee_bps": 125.0,
        "estimated_network_fee_eur": 0.0,
        "fusion_research_score": 0.8,
        "fusion_confidence": 0.8,
        "runner_persistence": 0.7,
        "launch_integrity_score": 0.9,
        "smart_distribution_score": 0.0,
        "coordinated_dump_risk": 0.0,
        "sellability_score": 0.9,
    }
    out = model.compute(
        {"genesis_score": 0.8, "p_x2_60m": None, "p_x5_60m": None, "p_x10_60m": None},
        f,
        10.0,
        cfg,
    )
    expected = 2 * (125 + 10 + 20 + 35) / 10000.0
    assert abs(out["estimated_roundtrip_cost_pct"] - expected) < 1e-12


def test_higher_protocol_fee_reduces_executable_edge():
    cfg = ExecutionConfig(
        priority_fee_bps=10,
        mev_adverse_bps=20,
        base_slippage_bps=35,
        impact_coefficient=0.0,
    )
    model = ExecutableAlphaModel()
    probs = {"genesis_score": 0.8, "p_x2_60m": None, "p_x5_60m": None, "p_x10_60m": None}
    base = {
        "liquidity_usd": 100_000,
        "fusion_research_score": 0.8,
        "fusion_confidence": 0.8,
        "runner_persistence": 0.7,
        "launch_integrity_score": 0.9,
        "smart_distribution_score": 0.0,
        "coordinated_dump_risk": 0.0,
        "sellability_score": 0.9,
    }
    cheap = model.compute(probs, {**base, "estimated_protocol_fee_bps": 30.0}, 10.0, cfg)
    expensive = model.compute(probs, {**base, "estimated_protocol_fee_bps": 125.0}, 10.0, cfg)
    assert expensive["expected_executable_edge"] < cheap["expected_executable_edge"]


def test_network_fee_is_scaled_as_roundtrip_fraction_of_position():
    cfg = ExecutionConfig(
        priority_fee_bps=0,
        mev_adverse_bps=0,
        base_slippage_bps=0,
        impact_coefficient=0.0,
    )
    model = ExecutableAlphaModel()
    f = {
        "liquidity_usd": 100_000,
        "estimated_protocol_fee_bps": 0.0,
        "estimated_network_fee_eur": 0.01,
        "fusion_research_score": 0.6,
        "sellability_score": 1.0,
    }
    out = model.compute({"genesis_score": 0.6}, f, 10.0, cfg)
    assert abs(out["estimated_roundtrip_cost_pct"] - 0.002) < 1e-12
