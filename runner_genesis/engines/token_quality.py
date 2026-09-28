from __future__ import annotations
from ..domain.state import TokenState


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


class TokenQualityEngine:
    """Point-in-time token risk/quality with explicit unknown-data handling."""

    def features(self, t: TokenState) -> dict[str, float | str | None]:
        weighted_penalties: list[tuple[float, float]] = []
        known = 0
        total = 6

        if t.dev_holdings_pct is not None:
            weighted_penalties.append((_clip(t.dev_holdings_pct / 0.25), 0.24)); known += 1
        if t.sniper_pct is not None:
            weighted_penalties.append((_clip(t.sniper_pct / 0.50), 0.18)); known += 1
        if t.bundle_pct is not None:
            weighted_penalties.append((_clip(t.bundle_pct / 0.50), 0.18)); known += 1
        if t.suspected_related_concentration_pct is not None:
            weighted_penalties.append((_clip(t.suspected_related_concentration_pct / 0.60), 0.18)); known += 1
        if t.liquidity_usd is not None:
            weighted_penalties.append((1.0 if t.liquidity_usd < 10_000 else _clip((30_000 - t.liquidity_usd) / 30_000), 0.12)); known += 1
        auth_risk = None
        if "mint_authority_active" in t.metadata or "freeze_authority_active" in t.metadata:
            auth_risk = 0.5 * float(bool(t.metadata.get("mint_authority_active"))) + 0.5 * float(bool(t.metadata.get("freeze_authority_active")))
            weighted_penalties.append((_clip(auth_risk), 0.10)); known += 1

        if weighted_penalties:
            wsum = sum(w for _, w in weighted_penalties)
            risk = sum(v * w for v, w in weighted_penalties) / max(wsum, 1e-9)
        else:
            risk = None
        completeness = known / total
        quality = (1.0 - float(risk)) * completeness if risk is not None else None
        return {
            "token_risk": risk,
            "token_quality_score": quality,
            "token_quality_data_quality": completeness,
            "liquidity_usd": t.liquidity_usd,
            "dev_holdings_pct": t.dev_holdings_pct,
            "sniper_pct": t.sniper_pct,
            "bundle_pct": t.bundle_pct,
            "related_concentration_pct": t.suspected_related_concentration_pct,
            "mint_freeze_authority_risk": auth_risk,
        }
