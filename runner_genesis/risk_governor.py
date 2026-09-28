from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from .ai_trader import TradeProposal, Action
from .domain.state import PaperAccount, TokenState


@dataclass
class RiskDecision:
    approved: bool
    proposal: TradeProposal
    reasons: list[str] = field(default_factory=list)


class RiskGovernor:
    def __init__(self, cfg):
        self.cfg = cfg

    def evaluate(
        self,
        p: TradeProposal,
        account: PaperAccount,
        token: TokenState,
        estimated_slippage_pct: float = 0.0,
        features: dict | None = None,
        now: datetime | None = None,
    ) -> RiskDecision:
        if now is not None:
            account.advance_accounting_day(now)
        f = features or {}
        r: list[str] = []
        if self.cfg.kill_switch:
            r.append('KILL_SWITCH')

        if p.action in (Action.ENTER, Action.ADD):
            estimated_fee=max(0.0,float(f.get('estimated_entry_fee_eur',0.0) or 0.0))
            entry_cash_cost=max(0.0,float(p.amount_eur))+estimated_fee
            max_from_pct = max(0.0, account.equity_eur * self.cfg.max_account_pct_per_trade)
            cap = min(self.cfg.max_position_eur, max_from_pct)
            current = account.positions.get(p.token_mint)
            current_cost = current.cost_basis_eur if current else 0.0
            if current_cost + entry_cash_cost > cap + 1e-9:
                r.append('MAX_POSITION')
            if entry_cash_cost > account.cash_eur + 1e-9:
                r.append('INSUFFICIENT_CASH')
            if p.token_mint not in account.positions and len(account.positions) >= self.cfg.max_simultaneous_positions:
                r.append('MAX_SIMULTANEOUS_POSITIONS')
            if account.daily_spend_eur + entry_cash_cost > self.cfg.max_daily_spend_eur + 1e-9:
                r.append('MAX_DAILY_SPEND')
            if token.liquidity_usd is None:
                r.append('LIQUIDITY_UNKNOWN')
            elif token.liquidity_usd < self.cfg.min_liquidity_usd:
                r.append('MIN_LIQUIDITY')
            if token.dev_holdings_pct is not None and token.dev_holdings_pct > self.cfg.max_dev_holdings_pct:
                r.append('DEV_CONCENTRATION')
            if token.sniper_pct is not None and token.sniper_pct > self.cfg.max_sniper_pct:
                r.append('SNIPER_CONCENTRATION')
            if token.bundle_pct is not None and token.bundle_pct > self.cfg.max_bundle_pct:
                r.append('BUNDLE_CONCENTRATION')
            if token.suspected_related_concentration_pct is not None and token.suspected_related_concentration_pct > self.cfg.max_suspected_related_concentration_pct:
                r.append('RELATED_CONCENTRATION')
            sellability = f.get('sellability_score')
            if sellability is not None and float(sellability) < self.cfg.min_sellability_score:
                r.append('SELLABILITY_RISK')
            manipulation = f.get('manipulation_risk')
            if manipulation is not None and float(manipulation) > self.cfg.max_manipulation_risk:
                r.append('MANIPULATION_RISK')
            if str(f.get('entry_validity', 'VALID')) == 'ENTRY_TOO_LATE':
                r.append('ENTRY_TOO_LATE')
            if bool(f.get('fusion_risk_veto', False)):
                r.append('FUSION_RISK_VETO')
            cohort_concentration = f.get('cohort_concentration')
            independence_ratio = f.get('independence_ratio')
            if (
                cohort_concentration is not None
                and float(cohort_concentration) > self.cfg.max_correlated_exposure_pct
                and (independence_ratio is None or float(independence_ratio) < 0.65)
            ):
                r.append('WALLET_CLUSTER_CONCENTRATION')
            cluster_id = f.get('dominant_actor_cluster_id')
            cluster_fraction = float(f.get('dominant_actor_cluster_fraction', 0.0) or 0.0)
            if (
                cluster_id
                and cluster_id != 'MIXED'
                and cluster_fraction >= float(self.cfg.min_cluster_fraction_for_exposure)
            ):
                cluster_exposure = sum(
                    float(position.cost_basis_eur)
                    for position in account.positions.values()
                    if getattr(position, 'risk_cluster_id', None) == cluster_id
                )
                cluster_limit = max(
                    0.0,
                    float(account.equity_eur) * float(self.cfg.max_correlated_exposure_pct),
                )
                if cluster_exposure + entry_cash_cost > cluster_limit + 1e-9:
                    r.append('MAX_WALLET_CLUSTER_EXPOSURE')

        if estimated_slippage_pct > self.cfg.max_slippage_pct:
            r.append('MAX_SLIPPAGE')

        # Drawdown/daily-loss limits stop new risk. They must not trap an already-open
        # position by rejecting a defensive reduction/exit after the limit has been hit.
        if p.action in (Action.ENTER, Action.ADD):
            dd = (account.peak_equity_eur - account.equity_eur) / max(account.peak_equity_eur, 1e-9)
            if dd > self.cfg.max_portfolio_drawdown_pct:
                r.append('MAX_DRAWDOWN')
            if account.daily_realized_pnl_eur < -self.cfg.max_daily_loss_eur:
                r.append('MAX_DAILY_LOSS')
        return RiskDecision(not r, p, r)
