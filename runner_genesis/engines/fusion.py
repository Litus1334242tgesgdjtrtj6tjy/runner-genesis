from __future__ import annotations

import math


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _logit(p: float) -> float:
    p = max(1e-4, min(1.0 - 1e-4, float(p)))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, x))))


class MultiBrainStateFusionEngine:
    """Reliability-aware research fusion.

    This deliberately outputs a *research score*, not a calibrated probability. Correlated
    modules are grouped so the system does not simply average every brain and accidentally
    count the same evidence several times.
    """

    def compute(self, features: dict, probs: dict) -> dict[str, float | str | bool]:
        calibrated = probs.get("genesis_prob") is not None
        genesis = float(
            probs.get("genesis_prob")
            if calibrated
            else probs.get("genesis_score", features.get("genesis_score", 0.0))
            or 0.0
        )
        data_q = _clip(float(features.get("data_quality_score", 0.0) or 0.0))
        smart = _clip(float(features.get("weighted_smart_capital_consensus", 0.0) or 0.0))
        accum = _clip(float(features.get("accumulation_score", 0.0) or 0.0))
        persistence = _clip(float(features.get("runner_persistence", 0.0) or 0.0))
        launch = _clip(float(features.get("launch_integrity_score", 0.5) or 0.5))
        dump = _clip(float(features.get("coordinated_dump_risk", 0.0) or 0.0))
        sellability = _clip(float(features.get("sellability_score", 0.0) or 0.0))
        world = _clip(float(features.get("world_smart_wave_score", 0.0) or 0.0))
        top_wave = _clip(float(features.get("top_trader_wave_score", 0.0) or 0.0))
        top_ind = _clip(float(features.get("top_trader_independence_ratio", 1.0) or 0.0))
        fomo = _clip(float(features.get("fomo_score", 0.0) or 0.0))
        market = max(-1.0, min(1.0, float(features.get("net_buy_pressure_60s", 0.0) or 0.0)))

        smart_group = _clip(0.68 * smart + 0.32 * accum)
        forward_group = world
        module_count = 3.0  # genesis + smart + world

        if features.get("mirofish_status") == "SIMULATION":
            mf_p = _clip(float(features.get("mirofish_persistence_frequency", 0.0) or 0.0))
            mf_c = _clip(float(features.get("mirofish_collapse_frequency", 0.0) or 0.0))
            forward_group = _clip(0.62 * world + 0.38 * _clip(mf_p - 0.75 * mf_c + 0.35))
            module_count += 1.0

        # Attention is useful only when on-chain evidence independently agrees.
        onchain_confirmation = _clip(0.55 * smart_group + 0.25 * persistence + 0.20 * max(0.0, market))
        attention_group = _clip((0.65 * top_wave * top_ind + 0.35 * fomo) * onchain_confirmation)
        if top_wave > 0 or fomo > 0:
            module_count += 1.0

        # FlyWire is experimental and has no calibrated direction. It may contribute a
        # small confidence/intensity modulation only when on-chain evidence is already
        # positive; it cannot create an entry signal by itself.
        fly_change = max(0.0, float(features.get("fly_state_change", 0.0) or 0.0))
        fly_support = _clip(math.tanh(fly_change) * onchain_confirmation)
        if fly_change > 0:
            module_count += 1.0

        score_logit = _logit(_clip(genesis))
        score_logit += 0.55 * (smart_group - 0.5)
        score_logit += 0.35 * (persistence - 0.5)
        score_logit += 0.30 * (forward_group - 0.5)
        score_logit += 0.22 * attention_group
        score_logit += 0.08 * fly_support
        score_logit += 0.35 * (launch - 0.5)
        score_logit -= 0.85 * dump
        score = _clip(_sigmoid(score_logit))

        completeness = min(1.0, module_count / 6.0)
        confidence = _clip(data_q * (0.55 + 0.45 * completeness))
        veto = (
            dump >= 0.78
            or sellability < 0.25
            or str(features.get("entry_validity", "NOT_CONFIRMED")) == "ENTRY_TOO_LATE"
        )
        return {
            "fusion_status": "TRAINED_MIXED" if calibrated else "RESEARCH_FUSION",
            "fusion_research_score": score,
            "fusion_confidence": confidence,
            "fusion_smart_group": smart_group,
            "fusion_forward_group": forward_group,
            "fusion_attention_group": attention_group,
            "fusion_fly_support": fly_support,
            "fusion_risk_veto": bool(veto),
        }
