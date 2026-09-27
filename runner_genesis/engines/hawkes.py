from __future__ import annotations
import math
from collections import defaultdict
from ..domain.events import MarketEvent, EventType

class HawkesCascadeEngine:
    """Interpretable marked Hawkes baseline. Thresholds are not treated as runner truth."""
    def __init__(self, half_life_seconds: float=25.0, baseline: float=0.05) -> None:
        self.half_life=half_life_seconds
        self.decay=math.log(2)/max(half_life_seconds,1e-6)
        self.baseline=baseline
        self.history=defaultdict(list)

    def observe_and_features(self, e: MarketEvent, mark: float=1.0) -> dict[str,float|str]:
        hist=self.history[e.token_mint]
        cutoff=e.timestamp.timestamp()-10*self.half_life
        hist[:] = [(t,m) for t,m in hist if t>=cutoff]
        now=e.timestamp.timestamp()
        intensity=self.baseline+sum(m*math.exp(-self.decay*(now-t)) for t,m in hist)
        if e.event_type in (EventType.BUY,EventType.WALLET_FUNDED,EventType.RUNNER_HOLDER_ENTRY,EventType.RUNNER_HOLDER_ADD,EventType.HOLDER_CREATED):
            hist.append((now,max(0.0,min(5.0,mark))))
        recent_mark=sum(m for t,m in hist if now-t <= self.half_life)
        r=recent_mark/max(1.0,len(hist))
        state="SUBCRITICAL" if r<0.6 else "NEAR_CRITICAL" if r<1.0 else "SUPERCRITICAL" if r<1.8 else "EXPANDING"
        return {"hawkes_intensity":float(intensity),"runner_cascade_r":float(r),"cascade_state":state}
