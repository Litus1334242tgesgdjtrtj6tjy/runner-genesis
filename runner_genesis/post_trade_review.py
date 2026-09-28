from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime

@dataclass
class TradeReview:
    token_mint:str
    opened_at:str
    closed_at:str
    realized_pnl_eur:float
    entry_thesis:dict
    exit_state:dict
    execution:dict
    lesson_candidates:list[str]

class PostTradeReviewEngine:
    """Creates research hypotheses only; never mutates production model/config."""
    def review(self,token_mint,opened_at,closed_at,pnl,entry_snapshot,exit_snapshot,fills)->TradeReview:
        lessons=[]
        ef=entry_snapshot.features if entry_snapshot else {}
        xf=exit_snapshot.features if exit_snapshot else {}
        if pnl<0 and float(ef.get('cluster_density',0))>0.6 and float(ef.get('related_concentration_pct',0))>0.3:
            lessons.append('Test stronger penalty for highly related clusters; validate OOS before promotion.')
        if pnl<0 and float(ef.get('capital_surprise',0))>0.8 and float(ef.get('wallet_quality',0))<0.2:
            lessons.append('Test interaction: Capital Surprise without historical wallet quality may be insufficient.')
        if pnl>0 and float(xf.get('runner_holder_retention',0))>0.7:
            lessons.append('Counterfactual: test whether later reduction policy improves runner capture without excess drawdown.')
        execution={'fills':len(fills),'fees_eur':sum(getattr(x,'fees_eur',0.0) for x in fills),'failed':sum(bool(getattr(x,'failed',False)) for x in fills)}
        return TradeReview(token_mint,str(opened_at),str(closed_at),float(pnl),dict(ef),dict(xf),execution,lessons)
