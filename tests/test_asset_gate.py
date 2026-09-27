from pathlib import Path
from datetime import datetime,timezone
from runner_genesis.config import load_settings
from runner_genesis.orchestrator import RunnerGenesisOmega
from runner_genesis.domain.events import MarketEvent,EventType

def test_unverified_asset_drops_price_mc(tmp_path,monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    eng=RunnerGenesisOmega(load_settings('config/default.yaml'))
    e=MarketEvent(event_id='x',timestamp=datetime.now(timezone.utc),token_mint='M',event_type=EventType.PRICE,price_usd=9,market_cap_usd=999,liquidity_usd=20000,asset_match_verified=False)
    eng.process(e)
    t=eng.store.token('M')
    assert t.price_usd is None
    assert t.market_cap_usd is None
