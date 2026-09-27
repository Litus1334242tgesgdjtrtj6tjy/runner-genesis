from datetime import datetime, timezone, timedelta

from runner_genesis.config import SmartCapitalConfig, PumpDiscoveryConfig
from runner_genesis.domain.events import MarketEvent, EventType
from runner_genesis.domain.state import WalletBuyObservation
from runner_genesis.state_store import MarketStateStore
from runner_genesis.engines.wallet_quality import WalletQualityEngine
from runner_genesis.engines.actor_graph import ActorGraphEngine
from runner_genesis.engines.discovery import PumpDiscoveryEngine
from runner_genesis.engines.smart_capital import SmartCapitalEngine


def ev(i, ts, mint='MINT', wallet='W1', typ=EventType.BUY, usd=100.0, price=1.0, mc=100_000.0, metadata=None):
    return MarketEvent(
        event_id=str(i), timestamp=ts, token_mint=mint, wallet=wallet,
        event_type=typ, usd_value=usd, price_usd=price, market_cap_usd=mc,
        liquidity_usd=50_000.0, metadata=metadata or {},
    )


def test_position_buy_sell_and_transfer_not_sell():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = MarketStateStore(); actor = ActorGraphEngine(); q = WalletQualityEngine()
    smart = SmartCapitalEngine(SmartCapitalConfig(), q, PumpDiscoveryEngine(PumpDiscoveryConfig()))
    buy = ev('b', t0, usd=100)
    store.apply(buy); actor.observe(buy); smart.observe(buy)
    transfer = MarketEvent(event_id='t', timestamp=t0+timedelta(seconds=1), token_mint='MINT', wallet='W1', counterparty='W2', event_type=EventType.TRANSFER, usd_value=50)
    store.apply(transfer); actor.observe(transfer); smart.observe(transfer)
    p = smart.positions[('W1', 'MINT')]
    assert p.buy_count == 1
    assert p.sell_count == 0
    sell = ev('s', t0+timedelta(seconds=2), typ=EventType.SELL, usd=40)
    store.apply(sell); actor.observe(sell); smart.observe(sell)
    assert p.sell_count == 1
    assert 0 < p.retained_fraction < 1


def test_same_funder_reduces_effective_wallet_count():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine()
    for i, w in enumerate(['A', 'B', 'C']):
        actor.observe(MarketEvent(event_id=f'f{i}', timestamp=t0+timedelta(seconds=i), token_mint='M', wallet=w, counterparty='FUNDER', event_type=EventType.WALLET_FUNDED, usd_value=1000))
    f = actor.cohort_features(['A', 'B', 'C'])
    assert f['raw_wallet_count'] == 3
    assert f['effective_wallet_count'] < 3
    assert f['same_funder_concentration'] == 1.0


def test_weighted_consensus_and_entry_distance_point_in_time():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = MarketStateStore(); actor = ActorGraphEngine(); q = WalletQualityEngine()
    smart = SmartCapitalEngine(SmartCapitalConfig(), q, PumpDiscoveryEngine(PumpDiscoveryConfig()))
    for w in ['A', 'B', 'C']:
        for j in range(30):
            store.resolve_wallet_observation(w, WalletBuyObservation(
                event_time=t0-timedelta(days=10+j), resolved_at=t0-timedelta(days=1), token_mint=f'OLD{j}',
                buy_eur=100, entry_mc=50_000, realized_return=1.2, runner_capture_ratio=0.7, hold_seconds=7200,
            ))
        ts = t0 + timedelta(minutes=3*['A','B','C'].index(w))
        e = ev(f'b{w}', ts, wallet=w, usd=100, price=1.0, metadata={'estimated_liquid_capital_usd':1000})
        store.apply(e); actor.observe(e); smart.observe(e)
    # two hours later, market price is 2x; only data available by this time is used.
    px = ev('px', t0+timedelta(hours=2), wallet=None, typ=EventType.PRICE, usd=0, price=2.0, mc=200_000)
    store.apply(px)
    f = smart.token_features('MINT', px.timestamp, store, actor)
    assert f['effective_wallet_count'] > 2.5
    assert f['weighted_smart_capital_consensus'] > 0.55
    assert 0.95 <= f['entry_distance_price'] <= 1.05
    assert f['signal_validity'] == 'VALID'
    assert f['entry_validity'] == 'VALID'
