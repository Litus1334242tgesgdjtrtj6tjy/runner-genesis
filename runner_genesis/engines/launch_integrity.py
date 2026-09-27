from __future__ import annotations

class LaunchIntegrityEngine:
    def features(self, token, cluster_features: dict | None = None) -> dict[str, float | str]:
        cluster_features = cluster_features or {}
        dev = max(0.0, float(token.dev_holdings_pct or 0.0))
        sniper = max(0.0, float(token.sniper_pct or 0.0))
        bundle = max(0.0, float(token.bundle_pct or 0.0))
        related = max(0.0, float(token.suspected_related_concentration_pct or 0.0))
        same_funder = max(0.0, float(cluster_features.get("cluster_mean_confidence", 0.0)))
        independent_diversity = max(0.0, 1.0 - min(1.0, related + 0.5 * same_funder))
        sellability = 1.0 if float(token.liquidity_usd or 0.0) >= 10_000 else max(0.0, float(token.liquidity_usd or 0.0) / 10_000)
        manipulation = min(1.0, 0.24 * min(1.0, dev / 0.20) + 0.24 * min(1.0, sniper / 0.35) + 0.20 * min(1.0, bundle / 0.35) + 0.22 * min(1.0, related / 0.45) + 0.10 * same_funder)
        dump = min(1.0, 0.55 * manipulation + 0.30 * (1.0 - sellability) + 0.15 * (1.0 - independent_diversity))
        integrity = max(0.0, 1.0 - 0.7 * manipulation - 0.3 * dump)
        state = "OK"
        if sellability < 0.25:
            state = "SELLABILITY_RISK"
        elif dump >= 0.72:
            state = "COORDINATED_DUMP_RISK"
        elif manipulation >= 0.68:
            state = "MANIPULATED_LAUNCH"
        elif max(dev, sniper, bundle, related) >= 0.45:
            state = "HIGH_CONCENTRATION_LAUNCH"
        return {
            "launch_integrity_score": integrity,
            "manipulation_risk": manipulation,
            "coordinated_dump_risk": dump,
            "sniper_concentration": sniper,
            "bundle_concentration": bundle,
            "same_funder_concentration": same_funder,
            "dev_related_exposure": max(dev, related),
            "real_holder_diversity": independent_diversity,
            "sellability_score": sellability,
            "launch_integrity_state": state,
        }
