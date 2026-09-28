from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from ..domain.events import MarketEvent, EventType
from ..state_store import MarketStateStore

class FundingGraphEngine:
    def __init__(self, lookback_seconds: int = 900) -> None:
        self.lookback = timedelta(seconds=lookback_seconds)

    def features(self, e: MarketEvent, store: MarketStateStore) -> dict[str,float]:
        if not e.wallet:
            return {"pre_funding_score":0.0,"funding_recency_seconds":1e9,"same_funder_cluster":0.0}
        w=store.wallet(e.wallet)
        recent=[x for x in w.funded_events if e.timestamp-self.lookback <= x[0] < e.timestamp]
        if not recent:
            return {"pre_funding_score":0.0,"funding_recency_seconds":1e9,"same_funder_cluster":0.0}
        last=max(recent,key=lambda x:x[0])
        rec=max(0.0,(e.timestamp-last[0]).total_seconds())
        size=float(last[1])
        buy=float(e.usd_value or 0.0)
        size_match=min(1.0, buy/max(size,1e-9)) if size>0 else 0.0
        score=max(0.0,min(1.0, (1.0-rec/self.lookback.total_seconds()) * (0.5+0.5*size_match)))
        return {"pre_funding_score":score,"funding_recency_seconds":rec,"same_funder_cluster":0.0}
