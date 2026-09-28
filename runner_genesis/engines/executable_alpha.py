from __future__ import annotations


class ExecutableAlphaModel:
    def compute(self, probs: dict, f: dict, position_eur: float, execution_cfg) -> dict[str, float | str]:
        liq = max(float(f.get('liquidity_usd') or 0.0), 1.0)
        impact_one_way = min(1.0, float(execution_cfg.impact_coefficient) * (float(position_eur) / liq))

        protocol_fee_bps = f.get('estimated_protocol_fee_bps')
        if protocol_fee_bps is None:
            protocol_fee_bps = float(execution_cfg.base_fee_bps)
        protocol_fee_bps = max(0.0, float(protocol_fee_bps))

        configured_notional_overhead_bps = max(0.0, float(execution_cfg.priority_fee_bps))
        adverse_bps = max(0.0, float(execution_cfg.mev_adverse_bps))
        base_slippage_bps = max(0.0, float(execution_cfg.base_slippage_bps))
        network_fee_eur = max(0.0, float(f.get('estimated_network_fee_eur') or 0.0))

        # Entry policy should compare expected return against the full round trip, not
        # one-way friction. This mirrors PAPER execution more closely and avoids promoting
        # tiny apparent edges that disappear after exit costs.
        one_way_notional_cost = (
            protocol_fee_bps
            + configured_notional_overhead_bps
            + adverse_bps
            + base_slippage_bps
        ) / 10000.0 + impact_one_way
        network_roundtrip_pct = (2.0 * network_fee_eur) / max(float(position_eur), 1e-9)
        roundtrip_costs = min(2.0, 2.0 * one_way_notional_cost + network_roundtrip_pct)

        max_size = liq * float(execution_cfg.max_liquidity_fraction)
        sellability = float(f.get('sellability_score') or 0.0)
        if sellability <= 0.0:
            sellability = max(0.0, min(1.0, liq / 100_000.0)) * (1 - min(1.0, impact_one_way * 4))

        p2 = probs.get('p_x2_60m')
        p5 = probs.get('p_x5_60m')
        p10 = probs.get('p_x10_60m')
        trained = all(x is not None for x in (p2, p5, p10))
        if trained:
            p2f, p5f, p10f = float(p2), float(p5), float(p10)
            gross = (p2f * 0.55 + p5f * 1.2 + p10f * 2.0) - (1 - max(p2f, p5f, p10f)) * 0.28
            status = 'MODEL_BASED'
        else:
            genesis = float(probs.get('genesis_score') or 0.0)
            fusion = float(f.get('fusion_research_score', genesis) or 0.0)
            fusion_conf = float(f.get('fusion_confidence', 0.0) or 0.0)
            persistence = float(f.get('runner_persistence') or 0.0)
            launch = float(f.get('launch_integrity_score') or 0.0)
            distribution = float(f.get('smart_distribution_score') or 0.0)
            dump = float(f.get('coordinated_dump_risk') or 0.0)
            gross = (
                0.22 * fusion
                + 0.10 * persistence
                + 0.06 * launch
                + 0.04 * fusion_conf
                - 0.18 * distribution
                - 0.12 * dump
                - 0.08
            )
            status = 'FUSION_HEURISTIC_UNTRAINED' if 'fusion_research_score' in f else 'HEURISTIC_UNTRAINED'

        edge = gross - roundtrip_costs
        return {
            'executable_alpha_status': status,
            'expected_executable_return': edge,
            'expected_executable_edge': edge,
            'max_executable_size_eur': max_size,
            'liquidity_confidence': max(0.0, min(1.0, liq / 50_000.0)),
            'sellability_score': sellability,
            'estimated_protocol_fee_bps': protocol_fee_bps,
            'estimated_network_fee_eur': network_fee_eur,
            'estimated_one_way_cost_pct': one_way_notional_cost + network_fee_eur / max(float(position_eur), 1e-9),
            'estimated_roundtrip_cost_pct': roundtrip_costs,
        }
