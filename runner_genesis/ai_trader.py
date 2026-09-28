from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum


class Action(StrEnum):
    PASS = 'PASS'
    WATCH = 'WATCH'
    ENTER = 'ENTER'
    ADD = 'ADD'
    HOLD = 'HOLD'
    PROTECT = 'PROTECT'
    PARTIAL_EXIT = 'PARTIAL_EXIT'
    REDUCE = 'REDUCE'
    EXIT = 'EXIT'
    KEEP_RUNNER_BAG = 'KEEP_RUNNER_BAG'


@dataclass
class TradeProposal:
    action: Action
    token_mint: str
    amount_eur: float = 0.0
    reduce_fraction: float = 0.0
    confidence: float = 0.0
    utility: float = 0.0
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


class AIPaperTrader:
    """Transparent paper policy. Risk Governor remains the higher authority."""

    def __init__(self, cfg, paper_only: bool = True):
        self.cfg = cfg
        self.paper_only = bool(paper_only)

    def _untrained_entry_allowed(self) -> bool:
        return bool(self.paper_only and getattr(self.cfg, 'allow_untrained_paper_entry', False))

    def decide(
        self,
        mint: str,
        features: dict,
        probs: dict,
        alpha: dict,
        persistence: dict,
        has_position: bool,
        current_cost: float = 0.0,
        adds: int = 0,
        current_quantity: float = 0.0,
        moonbag_target_quantity: float = 0.0,
    ) -> TradeProposal:
        calibrated = probs.get('genesis_prob') is not None
        genesis = float(probs.get('genesis_prob') if calibrated else probs.get('genesis_score') or 0.0)
        research_fusion = float(features.get('fusion_research_score', genesis) or 0.0)
        decision_score = genesis if calibrated else research_fusion
        fusion_confidence = float(features.get('fusion_confidence', 0.0) or 0.0)
        fusion_veto = bool(features.get('fusion_risk_veto', False))
        edge = float(alpha.get('expected_executable_edge', -1.0) or -1.0)
        hold = float(persistence.get('runner_persistence', 0.0) or 0.0)
        sellability = float(alpha.get('sellability_score', 0.0) or 0.0)
        risk = float(features.get('token_risk', 0.5) if features.get('token_risk') is not None else 0.5)
        consensus = float(features.get('weighted_smart_capital_consensus', features.get('smart_money_consensus', 0.0)) or 0.0)
        distribution = float(persistence.get('distribution_score', features.get('smart_distribution_score', 0.0)) or 0.0)
        manipulation = float(features.get('manipulation_risk', 0.0) or 0.0)
        entry_validity = str(features.get('entry_validity', 'NOT_CONFIRMED'))
        signal_validity = str(features.get('signal_validity', 'NOT_CONFIRMED'))
        data_quality = float(features.get('data_quality_score', 0.0) or 0.0)

        reasons: list[str] = []
        risks: list[str] = []
        reasons.append(('Calibrated Genesis' if calibrated else 'Research fusion score') + f' {decision_score:.2f}')
        if not calibrated:
            reasons.append(f'Fusion confidence {fusion_confidence:.2f}')
        if edge > 0:
            reasons.append(f'Executable edge proxy {edge:.3f}')
        if consensus >= 0.55:
            reasons.append(f'Weighted smart-capital consensus {consensus:.2f}')
        if hold >= 0.60:
            reasons.append(f'Persistence {hold:.2f}')
        if risk > 0.55:
            risks.append(f'Token risk {risk:.2f}')
        if manipulation > 0.60:
            risks.append(f'Launch manipulation risk {manipulation:.2f}')
        if sellability < 0.35:
            risks.append(f'Sellability {sellability:.2f}')
        if data_quality < 0.45:
            risks.append(f'Data quality {data_quality:.2f}')

        if not has_position:
            if entry_validity == 'ENTRY_TOO_LATE':
                return TradeProposal(Action.PASS, mint, confidence=decision_score, utility=edge, reasons=reasons, risks=risks + ['ENTRY_TOO_LATE'])
            if fusion_veto:
                return TradeProposal(Action.PASS, mint, confidence=decision_score, utility=edge, reasons=reasons, risks=risks + ['FUSION_RISK_VETO'])
            if signal_validity != 'VALID':
                return TradeProposal(Action.WATCH if decision_score >= self.cfg.min_genesis_to_watch else Action.PASS, mint, confidence=decision_score, utility=edge, reasons=reasons, risks=risks)
            if self.cfg.require_trained_for_entry and not calibrated and not self._untrained_entry_allowed():
                return TradeProposal(Action.WATCH, mint, confidence=decision_score, utility=edge, reasons=reasons + ['ENTRY_DISABLED_UNTIL_MODEL_TRAINED'], risks=risks)
            if edge >= self.cfg.min_entry_edge and decision_score >= self.cfg.min_genesis_to_watch and sellability >= 0.25:
                size = self.cfg.default_position_eur * max(0.5, min(2.0, 0.7 + decision_score + max(edge, 0)))
                utility = edge - 0.25 * risk - 0.20 * manipulation
                entry_reasons = list(reasons)
                if not calibrated:
                    entry_reasons.append('UNTRAINED_RESEARCH_PAPER_ENTRY')
                return TradeProposal(Action.ENTER, mint, size, confidence=decision_score, utility=utility, reasons=entry_reasons, risks=risks)
            return TradeProposal(Action.WATCH if decision_score >= self.cfg.min_genesis_to_watch else Action.PASS, mint, confidence=decision_score, utility=edge, reasons=reasons, risks=risks)

        if hold <= self.cfg.exit_below_hold_score or sellability <= 0.12 or distribution >= 0.82:
            return TradeProposal(Action.EXIT, mint, reduce_fraction=1.0, confidence=1 - hold, utility=-risk, reasons=reasons, risks=risks)
        if distribution >= 0.68:
            return TradeProposal(Action.PARTIAL_EXIT, mint, reduce_fraction=0.50, confidence=distribution, utility=edge, reasons=reasons, risks=risks)
        if hold <= self.cfg.reduce_below_hold_score or distribution > 0.55:
            return TradeProposal(Action.PROTECT, mint, reduce_fraction=0.35, confidence=max(1 - hold, distribution), utility=edge, reasons=reasons, risks=risks)
        if hold >= 0.78 and edge >= self.cfg.min_entry_edge * 0.8 and adds < self.cfg.max_adds_per_position and entry_validity == 'VALID':
            if not self.cfg.require_trained_for_entry or calibrated or self._untrained_entry_allowed():
                add_reasons = list(reasons)
                if not calibrated:
                    add_reasons.append('UNTRAINED_RESEARCH_PAPER_ADD')
                return TradeProposal(Action.ADD, mint, self.cfg.default_position_eur * 0.5, confidence=hold, utility=edge, reasons=add_reasons, risks=risks)
        if hold >= self.cfg.min_hold_score:
            return TradeProposal(Action.HOLD, mint, confidence=hold, utility=edge, reasons=reasons, risks=risks)

        # KEEP_RUNNER_BAG means "reduce once to a durable target", not "sell the same
        # fraction on every subsequent event". If a prior partial fill established an
        # absolute target quantity, only sell the excess above that target.
        qty = max(0.0, float(current_quantity or 0.0))
        target_qty = max(0.0, float(moonbag_target_quantity or 0.0))
        if target_qty > 0 and qty <= target_qty * (1.0 + 1e-9):
            return TradeProposal(
                Action.HOLD,
                mint,
                confidence=hold,
                utility=edge,
                reasons=reasons + ['RUNNER_BAG_TARGET_REACHED'],
                risks=risks,
            )
        if target_qty > 0 and qty > 0:
            reduce_fraction = max(0.0, min(1.0, (qty - target_qty) / qty))
        else:
            reduce_fraction = max(0.0, min(1.0, 1 - self.cfg.moonbag_fraction))
        if reduce_fraction <= 1e-9:
            return TradeProposal(Action.HOLD, mint, confidence=hold, utility=edge, reasons=reasons, risks=risks)
        return TradeProposal(
            Action.KEEP_RUNNER_BAG,
            mint,
            reduce_fraction=reduce_fraction,
            confidence=hold,
            utility=edge,
            reasons=reasons,
            risks=risks,
        )
