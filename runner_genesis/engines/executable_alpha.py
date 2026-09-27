from __future__ import annotations


class ExecutableAlphaModel:
    def compute(self, probs: dict, f: dict, position_eur: float, execution_cfg) -> dict[str, float | str]:
        liq = max(float(f.get('liquidity_usd') or 0.0), 1.0)
        impact = min(1.0, execution_cfg.impact_coefficient * (position_eur / liq))
        costs = (
            execution_cfg.base_fee_bps
            + execution_cfg.priority_fee_bps
            + execution_cfg.mev_adverse_bps
            + execution_cfg.base_slippage_bps
        ) / 10000.0 + impact
        max_size = liq * execution_cfg.max_liquidity_fraction
        sellability = float(f.get('sellability_score') or 0.0)
        if sellability <= 0.0:
            sellability = max(0.0, min(1.0, liq / 100_000.0)) * (1 - min(1.0, impact * 4))

        p2 = probs.get('p_x2_60m')
        p5 = probs.get('p_x5_60m')
        p10 = probs.get('p_x10_60m')
        trained = all(x is not None for x in (p2, p5, p10))
        if trained:
            p2f, p5f, p10f = float(p2), float(p5), float(p10)
            gross = (p2f * 0.55 + p5f * 1.2 + p10f * 2.0) - (1 - max(p2f, p5f, p10f)) * 0.28
            status = 'MODEL_BASED'
        else:
            # Research-only proxy used for ranking/watch state, not a calibrated return forecast.
            genesis = float(probs.get('genesis_score') or 0.0)
            persistence = float(f.get('runner_persistence') or 0.0)
            launch = float(f.get('launch_integrity_score') or 0.0)
            distribution = float(f.get('smart_distribution_score') or 0.0)
            gross = 0.18 * genesis + 0.12 * persistence + 0.08 * launch - 0.18 * distribution - 0.08
            status = 'HEURISTIC_UNTRAINED'
        edge = gross - costs
        return {
            'executable_alpha_status': status,
            'expected_executable_return': gross - costs,
            'expected_executable_edge': edge,
            'max_executable_size_eur': max_size,
            'liquidity_confidence': max(0.0, min(1.0, liq / 50_000.0)),
            'sellability_score': sellability,
            'estimated_roundtrip_cost_pct': costs,
        }
