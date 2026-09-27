from __future__ import annotations
from collections import defaultdict
import hashlib
import numpy as np
from ..domain.events import MarketEvent, EventType

class LatentJumpSDEEngine:
    """Trainable-ready latent jump-state baseline for irregular event streams.

    This is deliberately labelled a baseline: it is a real state-space implementation,
    not a claim that a fitted graph-neural Jump-SDE has already been trained.
    """
    def __init__(self, state_dim:int=32, seed:int=7) -> None:
        self.state_dim=state_dim
        self.states=defaultdict(lambda: np.zeros(state_dim,dtype=np.float32))
        self.last_ts={}
        rng=np.random.default_rng(seed)
        self.event_proj=rng.normal(0,0.12,(state_dim,8)).astype(np.float32)
        self.decay=np.linspace(0.015,0.12,state_dim,dtype=np.float32)

    def _embed(self,e:MarketEvent, extra:dict[str,float]|None=None)->np.ndarray:
        extra=extra or {}
        etypes=[EventType.BUY,EventType.SELL,EventType.WALLET_FUNDED,EventType.HOLDER_CREATED]
        buy=1.0 if e.event_type in (EventType.BUY,EventType.RUNNER_HOLDER_ENTRY,EventType.RUNNER_HOLDER_ADD) else 0.0
        sell=1.0 if e.event_type in (EventType.SELL,EventType.RUNNER_HOLDER_REDUCE,EventType.RUNNER_HOLDER_EXIT) else 0.0
        fund=1.0 if e.event_type==EventType.WALLET_FUNDED else 0.0
        holder=1.0 if e.event_type==EventType.HOLDER_CREATED else 0.0
        size=np.log1p(max(float(e.usd_value or 0),0.0))/12.0
        cs=float(extra.get('capital_surprise',0.0))
        quality=float(extra.get('wallet_quality',0.0))
        risk=float(extra.get('token_risk',0.0))
        return np.array([buy,sell,fund,holder,size,cs,quality,risk],dtype=np.float32)

    def observe(self,e:MarketEvent, extra:dict[str,float]|None=None)->dict[str,float]:
        x=self.states[e.token_mint]
        prev=self.last_ts.get(e.token_mint,e.timestamp)
        dt=max(0.0,(e.timestamp-prev).total_seconds())
        # deterministic continuous drift between irregular events
        x=x*np.exp(-self.decay*min(dt,300.0))
        z=self._embed(e,extra)
        jump=np.tanh(self.event_proj@z)
        x=np.tanh(x+jump)
        self.states[e.token_mint]=x.astype(np.float32)
        self.last_ts[e.token_mint]=e.timestamp
        return self.features(e.token_mint)

    def features(self,mint:str)->dict[str,float]:
        x=self.states[mint]
        return {
          'jump_state_norm':float(np.linalg.norm(x)),
          'jump_state_mean':float(x.mean()),
          'jump_state_positive_mass':float(np.maximum(x,0).mean()),
          'jump_state_negative_mass':float(np.maximum(-x,0).mean()),
        }

class NoOpJumpSDE:
    def observe(self,e,extra=None): return {'jump_state_norm':0.0,'jump_state_mean':0.0,'jump_state_positive_mass':0.0,'jump_state_negative_mass':0.0}
