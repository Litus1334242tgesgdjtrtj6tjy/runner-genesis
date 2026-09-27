from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib, math
import numpy as np
from .ai_trader import TradeProposal, Action
from .domain.state import TokenState
from .fees import PumpFeeSchedule

@dataclass
class PaperFill:
    token_mint: str
    side: str
    requested_eur: float
    filled_eur: float
    quantity: float
    reference_price: float
    execution_price: float
    slippage_pct: float
    fees_eur: float
    latency_ms: float
    failed: bool
    partial: bool
    timestamp: datetime
    reason: str=''
    protocol_fee_bps: float | None = None
    fee_source: str = 'CONFIG_FALLBACK'
    fee_schedule_version: str | None = None
    fee_confidence: float = 0.0

class PaperExecutionEngine:
    def __init__(self,cfg,seed:int=20260924):
        self.cfg=cfg
        self.seed=seed
        self.pump_fees=PumpFeeSchedule()

    def _rng(self,key:str):
        h=hashlib.sha256((str(self.seed)+key).encode()).digest()
        return np.random.default_rng(int.from_bytes(h[:8],'little'))

    def estimate_slippage(self,amount_eur:float,liquidity_usd:float)->float:
        liq=max(liquidity_usd,1.0)
        return self.cfg.base_slippage_bps/10000.0 + self.cfg.mev_adverse_bps/10000.0 + self.cfg.impact_coefficient*(amount_eur/liq)

    def execute(self,p:TradeProposal,token:TokenState,now:datetime,position_quantity:float=0.0)->PaperFill|None:
        if p.action not in (Action.ENTER,Action.ADD,Action.PROTECT,Action.PARTIAL_EXIT,Action.REDUCE,Action.EXIT,Action.KEEP_RUNNER_BAG): return None
        price=float(token.price_usd or 0.0); liq=float(token.liquidity_usd or 0.0)
        if price<=0 or liq<=0:
            return PaperFill(p.token_mint,'NA',0,0,0,price,price,1.0,0,0,True,False,now,'NO_EXECUTABLE_PRICE_OR_LIQUIDITY')
        rng=self._rng(f'{p.token_mint}|{now.isoformat()}|{p.action.value}')
        latency=max(0.0,float(rng.normal(self.cfg.latency_ms_mean,self.cfg.latency_ms_std)))
        fail_p=min(0.50,self.cfg.failed_tx_base_probability + max(0.0,10_000-liq)/10_000*0.08)
        failed=bool(rng.random()<fail_p)
        side='BUY' if p.action in (Action.ENTER,Action.ADD) else 'SELL'
        requested=float(p.amount_eur) if side=='BUY' else max(0.0,position_quantity*price*float(p.reduce_fraction or 1.0))
        if failed:
            return PaperFill(p.token_mint,side,requested,0,0,price,price,0,0,latency,True,False,now+timedelta(milliseconds=latency),'SIMULATED_TX_FAILURE')
        max_fill=max(0.0,liq*self.cfg.max_liquidity_fraction)
        filled=min(requested,max_fill) if self.cfg.partial_fill_enabled else requested
        partial=filled+1e-12<requested
        slip=self.estimate_slippage(filled,liq)
        direction=1 if side=='BUY' else -1
        exec_price=price*(1+direction*slip)
        fee_quote=self.pump_fees.quote(token)
        protocol_fee_bps=float(fee_quote.protocol_fee_bps) if fee_quote.protocol_fee_bps is not None else float(self.cfg.base_fee_bps)
        fee_rate=(protocol_fee_bps+float(self.cfg.priority_fee_bps))/10000.0
        fees=filled*fee_rate
        qty=filled/max(exec_price,1e-12)
        return PaperFill(
            p.token_mint,side,requested,filled,qty,price,exec_price,slip,fees,latency,
            False,partial,now+timedelta(milliseconds=latency),'',
            protocol_fee_bps,fee_quote.source,fee_quote.schedule_version,fee_quote.confidence,
        )
