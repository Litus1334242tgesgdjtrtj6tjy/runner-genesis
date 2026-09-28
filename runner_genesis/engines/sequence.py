from __future__ import annotations
from collections import defaultdict, deque
from ..domain.events import MarketEvent

class TemporalSequenceEngine:
    """Point-in-time sequence features; no future pattern matching is used at decision time."""
    def __init__(self,max_events:int=64):
        self.events=defaultdict(lambda:deque(maxlen=max_events))

    def observe_and_features(self,e:MarketEvent)->dict[str,float|str]:
        q=self.events[e.token_mint]
        q.append((e.timestamp,e.event_type.value,e.wallet))
        if len(q)<2:
            return {'sequence_event_count':float(len(q)),'mean_inter_event_seconds':0.0,'sequence_acceleration':0.0,'last_sequence':''}
        times=[x[0] for x in q]
        gaps=[max(0.0,(b-a).total_seconds()) for a,b in zip(times[:-1],times[1:])]
        recent=gaps[-5:]; prior=gaps[-10:-5]
        mean_recent=sum(recent)/max(len(recent),1)
        mean_prior=sum(prior)/max(len(prior),1) if prior else mean_recent
        accel=(mean_prior-mean_recent)/max(mean_prior,1e-9)
        seq='>'.join(x[1] for x in list(q)[-6:])
        return {'sequence_event_count':float(len(q)),'mean_inter_event_seconds':mean_recent,'sequence_acceleration':float(accel),'last_sequence':seq}
