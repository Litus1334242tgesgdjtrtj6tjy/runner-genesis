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
    assert f['same_funder_concentration_raw'] == 1.0
    assert 0.7 < f['same_funder_concentration'] < 1.0


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


def test_true_smart_capital_30d_uses_only_resolved_window_for_window_stats():
    now = datetime(2026, 3, 1, tzinfo=timezone.utc)
    store = MarketStateStore(); q = WalletQualityEngine()
    smart = SmartCapitalEngine(SmartCapitalConfig(), q, PumpDiscoveryEngine(PumpDiscoveryConfig()))
    wallet = 'WINDOW'
    observations = [
        WalletBuyObservation(
            event_time=now-timedelta(days=70), resolved_at=now-timedelta(days=60),
            token_mint='OLD', buy_eur=100, realized_return=10.0,
            runner_capture_ratio=0.9, hold_seconds=7200,
        ),
    ]
    for i in range(6):
        observations.append(WalletBuyObservation(
            event_time=now-timedelta(days=10-i), resolved_at=now-timedelta(days=6-i),
            token_mint=f'NEW{i}', buy_eur=100, realized_return=0.25 + 0.05*i,
            runner_capture_ratio=0.4, hold_seconds=3600,
        ))
    for obs in sorted(observations, key=lambda x: x.resolved_at):
        store.resolve_wallet_observation(wallet, obs)

    row = smart.wallet_metrics_window(wallet, now, store, 30)
    assert row['sample_size'] == 6
    assert row['tokens_10x'] == 0
    assert row['window_days'] == 30
    assert row['net_pnl'] is not None
    assert 0 <= row['smart_capital_30d_score'] <= 1

    emerg = smart.emerging_wallet_metrics(wallet, now, store)
    assert emerg['recent_sample_size_7d'] == 6
    assert 0 <= emerg['emerging_smart_wallet_score'] <= 1


def test_consensus_alone_does_not_bypass_conviction_gate():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cfg = SmartCapitalConfig(min_conviction=0.90)
    store = MarketStateStore(); actor = ActorGraphEngine(); q = WalletQualityEngine()
    smart = SmartCapitalEngine(cfg, q, PumpDiscoveryEngine(PumpDiscoveryConfig()))
    for w in ['A', 'B', 'C']:
        for j in range(30):
            store.resolve_wallet_observation(w, WalletBuyObservation(
                event_time=t0-timedelta(days=30+j),
                resolved_at=t0-timedelta(days=1),
                token_mint=f'OLD{w}{j}',
                buy_eur=100,
                entry_mc=50_000,
                realized_return=1.2,
                runner_capture_ratio=0.7,
                hold_seconds=7200,
            ))
        e = ev(f'b{w}', t0+timedelta(minutes=2), wallet=w, usd=10, price=1.0)
        store.apply(e); actor.observe(e); smart.observe(e)
    px = ev('px2', t0+timedelta(hours=2), wallet=None, typ=EventType.PRICE, usd=0, price=1.1, mc=110_000)
    store.apply(px)
    features = smart.token_features('MINT', px.timestamp, store, actor)
    assert features['weighted_smart_capital_consensus'] > 0
    assert features['conviction_score'] < 0.90
    assert features['signal_validity'] == 'NOT_CONFIRMED'


def test_high_degree_funder_is_downweighted_as_service_hub():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine()
    wallets = [f'W{i}' for i in range(20)]
    for i, w in enumerate(wallets):
        actor.observe_funding_link(w, 'COMMON_SERVICE', t0+timedelta(seconds=i), 0.95)
    f = actor.cohort_features(wallets)
    assert f['same_funder_concentration_raw'] == 1.0
    assert f['same_funder_concentration'] < 0.4
    assert f['effective_wallet_count'] > 5


def test_very_high_degree_funder_does_not_create_active_wallet_clique():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine(max_funder_pair_expansion=16)
    wallets = [f'H{i}' for i in range(40)]
    for i, w in enumerate(wallets):
        actor.observe_funding_link(w, 'LARGE_SERVICE', t0+timedelta(seconds=i), 0.95)

    active_wallet_edges = [
        (a, b) for a, b, d in actor.graph.edges(data=True)
        if a in wallets and b in wallets and float(d.get('confidence', 0.0)) >= 0.55
    ]
    features = actor.cohort_features(wallets)
    assert active_wallet_edges == []
    assert features['same_funder_concentration_raw'] == 1.0
    assert features['same_funder_concentration'] < 0.25
    assert features['effective_wallet_count'] > 30


def test_token_cluster_features_expire_old_cobuy_window():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine(coevent_window_seconds=120)
    for i, w in enumerate(['A', 'B', 'C']):
        actor.observe(ev(f'co{i}', t0+timedelta(seconds=i*10), wallet=w))
    fresh = actor.token_cluster_features('MINT', t0+timedelta(seconds=30))
    stale = actor.token_cluster_features('MINT', t0+timedelta(minutes=5))
    assert fresh['raw_wallet_count'] == 3
    assert stale['raw_wallet_count'] == 0
    assert stale['cluster_size'] == 0



def test_thousand_wallet_service_funder_stays_sparse():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine(max_funder_pair_expansion=32)
    wallets = [f'SCALE{i}' for i in range(1000)]
    for i, w in enumerate(wallets):
        actor.observe_funding_link(w, 'MEGA_SERVICE', t0+timedelta(seconds=i), 0.95)

    assert 'MEGA_SERVICE' in actor.hub_funders
    assert len(actor.funder_to_wallets['MEGA_SERVICE']) == 1000
    wallet_edges = [
        (a, b) for a, b in actor.graph.edges()
        if not str(a).startswith('funder:') and not str(b).startswith('funder:')
    ]
    assert len(wallet_edges) < 2000
    features = actor.cohort_features(wallets)
    assert features['effective_wallet_count'] > 700



def test_actor_graph_dedupes_replayed_event_ids():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine()
    a = ev('dup-a', t0, wallet='A')
    b = ev('dup-b', t0+timedelta(seconds=10), wallet='B')
    actor.observe(a)
    actor.observe(b)
    before = actor.link_confidence('A', 'B')
    actor.observe(b)
    after = actor.link_confidence('A', 'B')
    assert before > 0
    assert after == before



def test_out_of_order_history_never_links_to_future_buffered_buy():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine(coevent_window_seconds=120)
    future = ev('future-a', t0+timedelta(minutes=5), wallet='A')
    past = ev('past-b', t0, wallet='B')
    actor.observe(future)
    actor.observe(past)
    assert actor.link_confidence('A', 'B') == 0.0



def test_historical_smart_capital_ignores_orphan_sell_and_dedupes_events():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = MarketStateStore()
    smart = SmartCapitalEngine(
        SmartCapitalConfig(),
        WalletQualityEngine(),
        PumpDiscoveryEngine(PumpDiscoveryConfig()),
    )
    orphan_sell = MarketEvent(
        event_id='orphan-sell', timestamp=t0, token_mint='HIST', wallet='W',
        event_type=EventType.SELL, amount_token=50.0, usd_value=50.0,
    )
    buy = MarketEvent(
        event_id='hist-buy', timestamp=t0+timedelta(minutes=1), token_mint='HIST', wallet='W',
        event_type=EventType.BUY, amount_token=100.0, usd_value=100.0, price_usd=1.0,
    )
    sell = MarketEvent(
        event_id='hist-sell', timestamp=t0+timedelta(minutes=2), token_mint='HIST', wallet='W',
        event_type=EventType.SELL, amount_token=40.0, usd_value=48.0, price_usd=1.2,
    )

    smart.observe_historical_batch([orphan_sell, buy, sell, buy])
    p = smart.positions[('W', 'HIST')]
    assert p.buy_count == 1
    assert p.sell_count == 1
    assert p.bought_token == 100.0
    assert p.sold_token == 40.0
    assert abs(p.retained_fraction - 0.60) < 1e-12
    assert p.event_ids == ['hist-buy', 'hist-sell']



def test_smart_30d_score_is_not_boosted_by_old_resolved_wins():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    store = MarketStateStore()
    smart = SmartCapitalEngine(
        SmartCapitalConfig(),
        WalletQualityEngine(),
        PumpDiscoveryEngine(PumpDiscoveryConfig()),
    )
    for i in range(30):
        resolved = now - timedelta(days=90-i)
        store.resolve_wallet_observation('WITH_OLD', WalletBuyObservation(
            event_time=resolved-timedelta(days=1),
            resolved_at=resolved,
            token_mint=f'OLD{i}',
            buy_eur=100,
            realized_return=5.0,
            runner_capture_ratio=0.9,
            hold_seconds=12*3600,
        ))

    recent = [
        WalletBuyObservation(
            event_time=now-timedelta(days=10-i),
            resolved_at=now-timedelta(days=9-i),
            token_mint=f'R{i}',
            buy_eur=100,
            realized_return=0.10 if i % 2 == 0 else -0.05,
            runner_capture_ratio=None,
            hold_seconds=3600,
        )
        for i in range(8)
    ]
    for obs in recent:
        store.resolve_wallet_observation('WITH_OLD', obs)
        store.resolve_wallet_observation('RECENT_ONLY', WalletBuyObservation(**obs.__dict__))

    with_old = smart.wallet_metrics_window('WITH_OLD', now, store, 30)
    recent_only = smart.wallet_metrics_window('RECENT_ONLY', now, store, 30)
    assert with_old['sample_size'] == recent_only['sample_size'] == 8
    assert abs(with_old['smart_capital_30d_score'] - recent_only['smart_capital_30d_score']) < 1e-12
    assert abs(with_old['window_wallet_quality_score'] - recent_only['window_wallet_quality_score']) < 1e-12



def test_dominant_actor_cluster_fingerprint_repeats_across_tokens():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine(coevent_window_seconds=120)
    for mint in ["TOKEN_A", "TOKEN_B"]:
        actor.observe(ev(f"{mint}-A", t0, mint=mint, wallet="WALLET_A"))
        actor.observe(ev(f"{mint}-B", t0+timedelta(seconds=10), mint=mint, wallet="WALLET_B"))

    a = actor.token_cluster_features("TOKEN_A", t0+timedelta(seconds=20))
    b = actor.token_cluster_features("TOKEN_B", t0+timedelta(seconds=20))

    assert a["dominant_actor_cluster_id"] is not None
    assert a["dominant_actor_cluster_id"] == b["dominant_actor_cluster_id"]
    assert a["dominant_actor_cluster_fraction"] == 1.0
    assert b["dominant_actor_cluster_fraction"] == 1.0
