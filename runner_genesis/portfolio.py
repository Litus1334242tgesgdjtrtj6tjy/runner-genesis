from __future__ import annotations
from .domain.state import PaperAccount, PaperPosition
from .execution import PaperFill


class PortfolioLedger:
    def __init__(self, starting_cash_eur: float):
        self.account = PaperAccount(starting_cash_eur, starting_cash_eur)
        self.fills: list[PaperFill] = []
        self.marks: dict[str, float] = {}

    def apply_fill(self, fill: PaperFill) -> bool:
        self.account.advance_accounting_day(fill.timestamp)
        a = self.account
        if fill.failed:
            self.fills.append(fill)
            network_cost = max(0.0, float(fill.fees_eur or 0.0))
            if network_cost > 0:
                charged = min(network_cost, max(0.0, a.cash_eur))
                a.cash_eur -= charged
                a.realized_pnl_eur -= charged
                a.daily_realized_pnl_eur -= charged
                a.daily_spend_eur += charged
            return True
        if fill.filled_eur <= 0:
            return False

        if fill.side == 'BUY':
            total_cost = fill.filled_eur + fill.fees_eur
            if total_cost > a.cash_eur + 1e-9:
                return False
            self.fills.append(fill)
            p = a.positions.get(fill.token_mint)
            if p is None:
                p = PaperPosition(fill.token_mint, 0, 0, 0, fill.timestamp, fill.timestamp)
                a.positions[fill.token_mint] = p
            old_value = p.quantity * p.avg_entry_price
            new_qty = p.quantity + fill.quantity
            p.avg_entry_price = (old_value + fill.quantity * fill.execution_price) / max(new_qty, 1e-12)
            p.quantity = new_qty
            p.cost_basis_eur += total_cost
            p.last_updated_at = fill.timestamp
            fill_cluster = getattr(fill, 'risk_cluster_id', None)
            if fill_cluster:
                if p.risk_cluster_id is None or p.risk_cluster_id == fill_cluster:
                    p.risk_cluster_id = str(fill_cluster)
                    p.risk_cluster_fraction = max(
                        float(p.risk_cluster_fraction or 0.0),
                        float(getattr(fill, 'risk_cluster_fraction', 0.0) or 0.0),
                    )
                else:
                    # Multiple unrelated actor cohorts accumulated into the same position:
                    # mark it mixed rather than assigning all exposure to either clan.
                    p.risk_cluster_id = 'MIXED'
                    p.risk_cluster_fraction = 0.0
            if old_value > 0:
                p.adds += 1
            # Any new risk invalidates a previous absolute moonbag target; if the
            # position later de-risks again, a fresh target is anchored to the new size.
            if getattr(fill, 'proposal_action', None) in {'ENTER', 'ADD'}:
                p.moonbag_target_quantity = 0.0
                p.moonbag_locked_fraction = 0.0
            a.cash_eur -= total_cost
            a.daily_spend_eur += total_cost
            return True
        else:
            p = a.positions.get(fill.token_mint)
            if not p:
                return False
            before_qty = float(p.quantity)
            qty = min(before_qty, fill.quantity)
            if qty <= 0:
                return False
            self.fills.append(fill)

            if getattr(fill, 'proposal_action', None) == 'KEEP_RUNNER_BAG':
                reduce_fraction = max(0.0, min(1.0, float(getattr(fill, 'proposal_reduce_fraction', 0.0) or 0.0)))
                if p.moonbag_target_quantity <= 0 and reduce_fraction > 0:
                    p.moonbag_target_quantity = max(0.0, before_qty * (1.0 - reduce_fraction))

            fee_fraction = qty / max(fill.quantity, 1e-12)
            proceeds = qty * fill.execution_price - fill.fees_eur * fee_fraction
            avg_cost_per_unit = p.cost_basis_eur / max(p.quantity, 1e-12)
            cost_released = qty * avg_cost_per_unit
            pnl = proceeds - cost_released
            p.quantity -= qty
            p.cost_basis_eur = max(0, p.cost_basis_eur - cost_released)
            p.realized_pnl_eur += pnl
            a.cash_eur += proceeds
            a.realized_pnl_eur += pnl
            a.daily_realized_pnl_eur += pnl
            p.last_updated_at = fill.timestamp
            if p.moonbag_target_quantity > 0 and p.quantity <= p.moonbag_target_quantity * (1.0 + 1e-9):
                p.moonbag_locked_fraction = 1.0
            if p.quantity <= 1e-12:
                del a.positions[fill.token_mint]
            return True

    def mark_to_market(self, prices: dict[str, float]):
        a = self.account
        self.marks.update(prices)
        self.marks = {m: self.marks[m] for m in a.positions if m in self.marks}
        pos = sum(p.quantity * float(self.marks.get(m, p.avg_entry_price)) for m, p in a.positions.items())
        a.equity_eur = a.cash_eur + pos
        a.peak_equity_eur = max(a.peak_equity_eur, a.equity_eur)
        return a.equity_eur
