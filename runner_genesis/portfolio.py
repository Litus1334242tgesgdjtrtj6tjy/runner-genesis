from __future__ import annotations
from datetime import datetime
from .domain.state import PaperAccount, PaperPosition
from .execution import PaperFill

class PortfolioLedger:
    def __init__(self,starting_cash_eur:float):
        self.account=PaperAccount(starting_cash_eur,starting_cash_eur)
        self.fills:list[PaperFill]=[]

    def apply_fill(self,fill:PaperFill):
        self.fills.append(fill)
        if fill.failed or fill.filled_eur<=0: return
        a=self.account
        if fill.side=='BUY':
            total_cost=fill.filled_eur+fill.fees_eur
            if total_cost>a.cash_eur+1e-9: return
            p=a.positions.get(fill.token_mint)
            if p is None:
                p=PaperPosition(fill.token_mint,0,0,0,fill.timestamp,fill.timestamp)
                a.positions[fill.token_mint]=p
            old_value=p.quantity*p.avg_entry_price
            new_qty=p.quantity+fill.quantity
            p.avg_entry_price=(old_value+fill.quantity*fill.execution_price)/max(new_qty,1e-12)
            p.quantity=new_qty; p.cost_basis_eur+=total_cost; p.last_updated_at=fill.timestamp
            if old_value>0: p.adds+=1
            a.cash_eur-=total_cost; a.daily_spend_eur+=total_cost
        else:
            p=a.positions.get(fill.token_mint)
            if not p: return
            qty=min(p.quantity,fill.quantity)
            proceeds=qty*fill.execution_price-fill.fees_eur
            avg_cost_per_unit=p.cost_basis_eur/max(p.quantity,1e-12)
            cost_released=qty*avg_cost_per_unit
            pnl=proceeds-cost_released
            p.quantity-=qty; p.cost_basis_eur=max(0,p.cost_basis_eur-cost_released); p.realized_pnl_eur+=pnl
            a.cash_eur+=proceeds; a.realized_pnl_eur+=pnl; p.last_updated_at=fill.timestamp
            if p.quantity<=1e-12: del a.positions[fill.token_mint]

    def mark_to_market(self,prices:dict[str,float]):
        a=self.account
        pos=sum(p.quantity*float(prices.get(m,p.avg_entry_price)) for m,p in a.positions.items())
        a.equity_eur=a.cash_eur+pos
        a.peak_equity_eur=max(a.peak_equity_eur,a.equity_eur)
        return a.equity_eur
