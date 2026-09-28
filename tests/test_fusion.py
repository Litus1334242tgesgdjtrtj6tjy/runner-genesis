from runner_genesis.ai_trader import AIPaperTrader, Action
from runner_genesis.config import TraderConfig
from runner_genesis.engines.fusion import MultiBrainStateFusionEngine


def _base_features():
    return {
        "data_quality_score": 0.9,
        "weighted_smart_capital_consensus": 0.75,
        "accumulation_score": 0.75,
        "runner_persistence": 0.72,
        "launch_integrity_score": 0.85,
        "coordinated_dump_risk": 0.08,
        "sellability_score": 0.90,
        "world_smart_wave_score": 0.72,
        "top_trader_wave_score": 0.65,
        "top_trader_independence_ratio": 0.90,
        "fomo_score": 0.35,
        "net_buy_pressure_60s": 0.65,
        "entry_validity": "VALID",
        "signal_validity": "VALID",
    }


def test_fusion_rewards_independent_onchain_confirmation():
    eng = MultiBrainStateFusionEngine()
    good = _base_features()
    bad = dict(good)
    bad.update({
        "weighted_smart_capital_consensus": 0.05,
        "accumulation_score": 0.05,
        "runner_persistence": 0.10,
        "world_smart_wave_score": 0.10,
        "net_buy_pressure_60s": -0.5,
        "launch_integrity_score": 0.35,
        "coordinated_dump_risk": 0.75,
    })
    probs = {"genesis_prob": None, "genesis_score": 0.62}
    a = eng.compute(good, probs)
    b = eng.compute(bad, probs)
    assert a["fusion_research_score"] > b["fusion_research_score"]
    assert 0 <= a["fusion_research_score"] <= 1


def test_fomo_alone_cannot_create_strong_fusion_signal():
    eng = MultiBrainStateFusionEngine()
    f = {
        "data_quality_score": 0.9,
        "weighted_smart_capital_consensus": 0.0,
        "accumulation_score": 0.0,
        "runner_persistence": 0.0,
        "launch_integrity_score": 0.7,
        "coordinated_dump_risk": 0.0,
        "sellability_score": 0.8,
        "world_smart_wave_score": 0.0,
        "top_trader_wave_score": 0.0,
        "top_trader_independence_ratio": 1.0,
        "fomo_score": 1.0,
        "net_buy_pressure_60s": 0.0,
    }
    out = eng.compute(f, {"genesis_prob": None, "genesis_score": 0.25})
    assert out["fusion_attention_group"] == 0.0
    assert out["fusion_research_score"] < 0.5


def test_fusion_sets_risk_veto_for_dump_sellability_or_late_entry():
    eng = MultiBrainStateFusionEngine()
    f = _base_features()
    f["coordinated_dump_risk"] = 0.90
    out = eng.compute(f, {"genesis_prob": None, "genesis_score": 0.8})
    assert out["fusion_risk_veto"] is True


def test_untrained_research_entry_allowed_only_in_paper_mode():
    cfg = TraderConfig(
        require_trained_for_entry=True,
        allow_untrained_paper_entry=True,
        min_genesis_to_watch=0.55,
        min_entry_edge=0.01,
    )
    f = _base_features()
    f.update({
        "fusion_research_score": 0.80,
        "fusion_confidence": 0.80,
        "fusion_risk_veto": False,
        "token_risk": 0.15,
        "manipulation_risk": 0.10,
    })
    probs = {"genesis_prob": None, "genesis_score": 0.60}
    alpha = {"expected_executable_edge": 0.08, "sellability_score": 0.90}
    persistence = {"runner_persistence": 0.70, "distribution_score": 0.10}

    paper = AIPaperTrader(cfg, paper_only=True).decide("M", f, probs, alpha, persistence, False)
    non_paper = AIPaperTrader(cfg, paper_only=False).decide("M", f, probs, alpha, persistence, False)

    assert paper.action == Action.ENTER
    assert "UNTRAINED_RESEARCH_PAPER_ENTRY" in paper.reasons
    assert non_paper.action == Action.WATCH
    assert "ENTRY_DISABLED_UNTIL_MODEL_TRAINED" in non_paper.reasons
