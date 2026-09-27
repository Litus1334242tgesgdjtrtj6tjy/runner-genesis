from datetime import datetime,timezone,timedelta
from runner_genesis.state_store import MarketStateStore
from runner_genesis.domain.events import MarketEvent,EventType
from runner_genesis.engines.capital_surprise import CapitalSurpriseEngine

def ev(i,size,ts,w='W'):
    return MarketEvent(event_id=str(i),timestamp=ts,token_mint='M',wallet=w,event_type=EventType.BUY,usd_value=size,price_usd=1,liquidity_usd=100000)

def test_current_trade_not_in_own_history():
    s=MarketStateStore(); e=CapitalSurpriseEngine(min_history=3)
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    for i,x in enumerate([10,11,9,10,12]): s.apply(ev(i,x,t+timedelta(seconds=i)))
    cur=ev(99,100,t+timedelta(seconds=10))
    r=e.compute(cur,s)
    assert r.history_n==5
    assert r.relative_size>5
    assert r.capital_surprise>0.5
