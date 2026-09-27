from __future__ import annotations
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
from .domain.events import MarketEvent,EventType

def make_demo(path:str|Path)->Path:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    t0=datetime(2026,1,1,tzinfo=timezone.utc); mint='DEMO_MINT_111111111111111111111111111111'
    ev=[]
    ev.append(MarketEvent(event_id='e0',timestamp=t0,token_mint=mint,event_type=EventType.TOKEN_CREATED,price_usd=0.00010,market_cap_usd=30_000,liquidity_usd=50_000,source='demo'))
    for i in range(1,30):
        ts=t0+timedelta(seconds=i*4)
        price=0.00010*(1+0.045*i)
        ev.append(MarketEvent(event_id=f'e{i}',timestamp=ts,token_mint=mint,wallet=f'W{i%7}',event_type=EventType.BUY,usd_value=80+35*(i%5),price_usd=price,market_cap_usd=30_000*(price/0.0001),liquidity_usd=50_000+300*i,token_age_seconds=i*4,metadata={'dev_holdings_pct':0.04,'sniper_pct':0.10,'bundle_pct':0.08}))
    for j in range(5):
        i=30+j; ts=t0+timedelta(seconds=130+j*8); price=0.00010*2.2*(1-0.03*j)
        ev.append(MarketEvent(event_id=f'e{i}',timestamp=ts,token_mint=mint,wallet=f'W{j}',event_type=EventType.SELL,usd_value=70,price_usd=price,market_cap_usd=30_000*(price/0.0001),liquidity_usd=62_000,token_age_seconds=130+j*8))
    with p.open('w',encoding='utf-8') as f:
        for x in ev: f.write(x.model_dump_json()+'\n')
    return p
