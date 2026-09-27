from datetime import datetime, timezone, timedelta
from runner_genesis.config import MiroFishConfig, FomoConfig
from runner_genesis.domain.state import TokenState
from runner_genesis.engines.mirofish import MiroFishRolloutEngine
from runner_genesis.engines.launch_integrity import LaunchIntegrityEngine
from runner_genesis.engines.fomo import FomoEngine
from runner_genesis.engines.genesis import RunnerGenesisModel


def test_untrained_genesis_does_not_emit_fake_probabilities():
    m = RunnerGenesisModel(None)
    out = m.predict({'weighted_smart_capital_consensus':0.8, 'launch_integrity_score':0.8})
    assert m.model_status == 'UNTRAINED'
    assert out['genesis_score'] is not None
    assert out['genesis_prob'] is None
    assert out['p_x2_60m'] is None


def test_mirofish_seeded_rollouts_are_deterministic_and_labeled_simulation():
    cfg = MiroFishConfig(enabled=True, num_rollouts=32, require_min_data_quality=0.0, rollout_timeout_ms=1000)
    m = MiroFishRolloutEngine(cfg)
    t = datetime(2026,1,1,tzinfo=timezone.utc)
    f = {'data_quality_score':0.9,'weighted_smart_capital_consensus':0.7,'accumulation_score':0.8,'runner_persistence':0.7,'launch_integrity_score':0.8,'coordinated_dump_risk':0.1}
    a = m.rollouts('M', t, f); b = m.rollouts('M', t, f)
    assert a == b
    assert a['mirofish_status'] == 'SIMULATION'
    assert 0 <= a['mirofish_persistence_frequency'] <= 1


def test_launch_integrity_high_concentration_is_risky():
    token = TokenState('M', price_usd=1, market_cap_usd=100_000, liquidity_usd=4_000, dev_holdings_pct=0.4, sniper_pct=0.6, bundle_pct=0.6, suspected_related_concentration_pct=0.8)
    f = LaunchIntegrityEngine().features(token, {'effective_wallet_count':1.0,'cluster_mean_confidence':0.9,'same_funder_concentration':1.0})
    assert f['manipulation_risk'] > 0.6
    assert f['sellability_score'] < 0.2


def test_fomo_optional_and_point_in_time_window():
    t = datetime(2026,1,1,tzinfo=timezone.utc)
    disabled = FomoEngine(FomoConfig(enabled=False))
    assert disabled.features('M', t)['fomo_status'] == 'DISABLED'
    eng = FomoEngine(FomoConfig(enabled=True, maximum_source_age_seconds=300, window_seconds=120))
    eng.ingest({'token_mint':'M','timestamp':t-timedelta(seconds=20),'source':'PUMP','actor_key':'a','confidence':0.9})
    eng.ingest({'token_mint':'M','timestamp':t-timedelta(seconds=10),'source':'KOL','actor_key':'b','confidence':0.9})
    eng.ingest({'token_mint':'M','timestamp':t+timedelta(seconds=10),'source':'FUTURE','actor_key':'c','confidence':1.0})
    f = eng.features('M', t)
    assert f['fomo_independent_source_count'] == 2


def test_mirofish_skips_low_signal_candidates_even_when_enabled():
    cfg = MiroFishConfig(enabled=True, require_min_data_quality=0.0)
    m = MiroFishRolloutEngine(cfg)
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    f = {
        'data_quality_score': 0.9,
        'weighted_smart_capital_consensus': 0.0,
        'accumulation_score': 0.0,
        'top_trader_wave_score': 0.0,
        'fomo_score': 0.0,
    }
    out = m.rollouts('M', t, f)
    assert out['mirofish_status'] == 'NOT_TRIGGERED'


def test_fomo_dedupes_provider_callout_id():
    t = datetime(2026,1,1,tzinfo=timezone.utc)
    eng = FomoEngine(FomoConfig(enabled=True))
    row = {
        'token_mint':'M',
        'timestamp':t,
        'source':'FOMOSCAN_PUMP_CALLOUT',
        'actor_key':'a',
        'confidence':0.9,
        'metadata':{'raw_id':'callout-123'},
    }
    assert eng.ingest(row) is not None
    assert eng.ingest(row) is None
    assert len(eng.recent('M')) == 1



def test_launch_integrity_uses_same_population_for_independence_ratio():
    token = TokenState(
        'M',
        price_usd=1,
        market_cap_usd=100_000,
        liquidity_usd=100_000,
    )
    token.buyers = {f'B{i}' for i in range(100)}
    features = LaunchIntegrityEngine().features(
        token,
        {
            'effective_wallet_count': 3.6,
            'raw_wallet_count': 4.0,
            'independence_ratio': 0.9,
            'cluster_mean_confidence': 0.0,
            'same_funder_concentration': 0.0,
        },
    )
    assert abs(features['real_holder_diversity'] - 0.9) < 1e-12
    assert features['launch_integrity_score'] > 0.8
