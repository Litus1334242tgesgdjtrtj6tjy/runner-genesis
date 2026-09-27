from __future__ import annotations
from datetime import timedelta
from ..domain.events import EventType
from ..domain.state import TokenState

class MarketAccelerationEngine:
    def features(self, token: TokenState, now) -> dict[str,float]:
        windows=(15,60,300)
        out={}
        for sec in windows:
            ev=[e for e in token.events if 0 <= (now-e.timestamp).total_seconds() <= sec]
            buys=[e for e in ev if e.event_type in (EventType.BUY,EventType.RUNNER_HOLDER_ENTRY,EventType.RUNNER_HOLDER_ADD)]
            sells=[e for e in ev if e.event_type in (EventType.SELL,EventType.RUNNER_HOLDER_REDUCE,EventType.RUNNER_HOLDER_EXIT)]
            buyers={e.wallet for e in buys if e.wallet}
            buy_usd=sum(float(e.usd_value or 0) for e in buys)
            sell_usd=sum(float(e.usd_value or 0) for e in sells)
            out[f"buyers_{sec}s"] = float(len(buyers))
            out[f"buy_velocity_{sec}s"] = buy_usd/sec
            out[f"sell_velocity_{sec}s"] = sell_usd/sec
            out[f"net_buy_pressure_{sec}s"] = (buy_usd-sell_usd)/max(buy_usd+sell_usd,1.0)
        out["buyer_acceleration"]=(out["buyers_15s"]/15.0)-(out["buyers_60s"]/60.0)
        out["volume_acceleration"]=(out["buy_velocity_15s"]-out["buy_velocity_60s"])
        return out
