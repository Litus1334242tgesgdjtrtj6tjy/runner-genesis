from __future__ import annotations
from typing import Any
from ..domain.state import TokenState


def _known(v: Any) -> bool:
    return v is not None


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


class LaunchIntegrityEngine:
    """Evidence-based launch/manipulation risk. Outputs research scores, not accusations."""

    def features(self, token: TokenState, graph_features: dict[str, float] | None = None) -> dict[str, float | str]:
        g = graph_features or {}
        evidence: list[tuple[float, float]] = []

        if _known(token.dev_holdings_pct):
            evidence.append((_clip(float(token.dev_holdings_pct) / 0.25), 0.18))
        if _known(token.sniper_pct):
            evidence.append((_clip(float(token.sniper_pct) / 0.50), 0.16))
        if _known(token.bundle_pct):
            evidence.append((_clip(float(token.bundle_pct) / 0.50), 0.14))
        if _known(token.suspected_related_concentration_pct):
            evidence.append((_clip(float(token.suspected_related_concentration_pct) / 0.60), 0.16))

        same_funder = g.get("same_funder_concentration")
        if same_funder is not None:
            evidence.append((_clip(float(same_funder)), 0.12))

        cluster = g.get("cluster_mean_confidence")
        if cluster is not None:
            evidence.append((_clip(float(cluster)), 0.08))

        wash = token.metadata.get("wash_score")
        if wash is not None:
            evidence.append((_clip(float(wash)), 0.10))

        deployer = token.metadata.get("deployer_risk_score")
        if deployer is not None:
            evidence.append((_clip(float(deployer)), 0.06))

        liq = token.liquidity_usd
        mc = token.market_cap_usd
        if liq is not None and mc is not None and mc > 0:
            liq_ratio = liq / mc
            evidence.append((_clip((0.10 - liq_ratio) / 0.10) if liq_ratio < 0.10 else 0.0, 0.08))

        if evidence:
            total_w = sum(w for _, w in evidence)
            manipulation = sum(v * w for v, w in evidence) / max(total_w, 1e-9)
            data_quality = min(1.0, total_w / 0.80)
        else:
            manipulation = 0.0
            data_quality = 0.0

        independent_buyers = float(g.get("effective_wallet_count", 0.0) or 0.0)
        raw_buyers = max(float(len(token.buyers)), 1.0)
        diversity = _clip(independent_buyers / raw_buyers) if token.buyers else 0.0

        externally_supplied_sellability = token.metadata.get("sellability_score")
        if externally_supplied_sellability is not None:
            sellability = _clip(float(externally_supplied_sellability))
        elif liq is not None:
            liq_score = _clip(liq / 100_000.0)
            sellability = _clip(liq_score * (1.0 - 0.70 * manipulation))
        else:
            sellability = 0.0

        integrity = _clip((1.0 - manipulation) * (0.55 + 0.45 * diversity))
        dump_risk = _clip(0.65 * manipulation + 0.35 * (1.0 - sellability))
        if data_quality < 0.25:
            state = "INSUFFICIENT_DATA"
        elif dump_risk >= 0.75:
            state = "COORDINATED_DUMP_RISK"
        elif manipulation >= 0.68:
            state = "MANIPULATED_LAUNCH"
        elif integrity >= 0.65:
            state = "ACCEPTABLE"
        else:
            state = "CAUTION"

        return {
            "launch_integrity_score": integrity,
            "manipulation_risk": manipulation,
            "coordinated_dump_risk": dump_risk,
            "real_holder_diversity": diversity,
            "sellability_score": sellability,
            "launch_integrity_data_quality": data_quality,
            "launch_integrity_state": state,
        }
