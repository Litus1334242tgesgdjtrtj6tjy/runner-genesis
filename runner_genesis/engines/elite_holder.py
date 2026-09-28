from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from ..domain.events import MarketEvent, EventType
from .wallet_quality import WalletQualityEngine
from ..state_store import MarketStateStore

class EliteRunnerHolderEngine:
    def __init__(self, wallet_quality:WalletQualityEngine) -> None:
        self.wallet_quality=wallet_quality
        self.max_acquired=defaultdict(lambda:defaultdict(float))
        self.current=defaultdict(lambda:defaultdict(float))

    def observe_and_features(self,e:MarketEvent,store:MarketStateStore)->dict[str,float|str]:
        if e.wallet:
            amount=max(float(e.usd_value or 0.0),0.0)
            cur=self.current[e.token_mint][e.wallet]
            if e.event_type in (EventType.BUY,EventType.RUNNER_HOLDER_ENTRY,EventType.RUNNER_HOLDER_ADD):
                cur+=amount
            elif e.event_type in (EventType.SELL,EventType.RUNNER_HOLDER_REDUCE,EventType.RUNNER_HOLDER_EXIT):
                cur=max(0.0,cur-amount)
            self.current[e.token_mint][e.wallet]=cur
            self.max_acquired[e.token_mint][e.wallet]=max(self.max_acquired[e.token_mint][e.wallet],cur)
        return self.features(e.token_mint,e.timestamp,store)

    def features(self,mint,as_of,store)->dict[str,float|str]:
        weighted_cur=0.0; weighted_max=0.0; elite=0; holders=0; leaders=0; quality_sum=0.0
        for w,mx in self.max_acquired[mint].items():
            if mx<=0: continue
            q=self.wallet_quality.compute(w,as_of,store)
            weight=max(0.05,q.quality)
            cur=self.current[mint].get(w,0.0)
            weighted_cur+=weight*cur; weighted_max+=weight*mx
            if q.role in ('ELITE_RUNNER_HOLDER','RUNNER_HOLDER'): holders+=1
            if q.role=='ELITE_RUNNER_HOLDER': elite+=1
            if q.role=='LEADER': leaders+=1
            quality_sum+=q.quality
        retention=weighted_cur/max(weighted_max,1e-9) if weighted_max>0 else 0.0
        consensus=min(1.0,0.55*retention+0.15*min(1,holders/3)+0.15*min(1,elite/2)+0.15*min(1,quality_sum/2))
        if consensus>=0.78: state='STRONG_ACCUMULATION'
        elif consensus>=0.62: state='ACCUMULATION'
        elif retention>=0.65: state='HOLDING'
        elif retention>=0.40: state='MIXED'
        elif retention>=0.20: state='EARLY_DISTRIBUTION'
        else: state='EXIT' if weighted_max>0 else 'UNKNOWN'
        return {
          'runner_holder_retention':float(retention),
          'elite_holder_count':float(elite),
          'runner_holder_count':float(holders),
          'leader_count':float(leaders),
          'smart_money_consensus':float(consensus),
          'smart_capital_state':state,
        }
