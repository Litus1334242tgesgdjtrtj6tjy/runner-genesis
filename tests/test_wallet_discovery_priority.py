from datetime import datetime, timedelta, timezone

from runner_genesis.config import ExternalDiscoveryConfig
from runner_genesis.engines.wallet_discovery_priority import WalletDiscoveryPriorityEngine


def test_priority_weights_are_normalized_and_bounded():
    cfg = ExternalDiscoveryConfig()
    eng = WalletDiscoveryPriorityEngine(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = eng.score(
        {
            "wallet_address": "W",
            "rank": 1,
            "source_confidence": 0.9,
            "observed_at": now,
        },
        smart_metrics={
            "smart_capital_30d_score": 0.8,
            "emerging_smart_wallet_score": 0.7,
            "data_quality_score": 0.8,
        },
        discovery_context={
            "pump_rank_velocity": 5.0,
            "pump_rank_acceleration": 10.0,
        },
        independence_score=0.9,
        now=now,
    )
    assert 0.0 <= out["wallet_discovery_priority_score"] <= 1.0
    assert abs(sum(out["wallet_discovery_priority_weights"].values()) - 1.0) < 1e-12


def test_verified_emerging_wallet_can_outrank_weak_external_top_candidate():
    cfg = ExternalDiscoveryConfig()
    eng = WalletDiscoveryPriorityEngine(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    weak_top = eng.score(
        {
            "wallet_address": "TOP",
            "rank": 50,
            "source_confidence": 0.9,
            "observed_at": now,
        },
        smart_metrics={
            "smart_capital_30d_score": 0.0,
            "emerging_smart_wallet_score": 0.0,
            "data_quality_score": 0.0,
        },
        discovery_context={},
        independence_score=1.0,
        now=now,
    )
    strong_emerging = eng.score(
        {
            "wallet_address": "EMERGING",
            "rank": None,
            "source_confidence": 0.55,
            "observed_at": now - timedelta(minutes=3),
        },
        smart_metrics={
            "smart_capital_30d_score": 0.88,
            "emerging_smart_wallet_score": 0.82,
            "data_quality_score": 0.85,
        },
        discovery_context={},
        independence_score=0.95,
        now=now,
    )
    assert (
        strong_emerging["wallet_discovery_priority_score"]
        > weak_top["wallet_discovery_priority_score"]
    )


def test_stale_activity_decays_without_erasing_good_onchain_quality():
    cfg = ExternalDiscoveryConfig(wallet_priority_activity_half_life_seconds=600)
    eng = WalletDiscoveryPriorityEngine(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    common = {
        "wallet_address": "W",
        "rank": None,
        "source_confidence": 0.6,
    }
    metrics = {
        "smart_capital_30d_score": 0.75,
        "emerging_smart_wallet_score": 0.65,
        "data_quality_score": 0.8,
    }
    recent = eng.score(
        {**common, "observed_at": now},
        smart_metrics=metrics,
        discovery_context={},
        independence_score=0.9,
        now=now,
    )
    stale = eng.score(
        {**common, "observed_at": now - timedelta(hours=2)},
        smart_metrics=metrics,
        discovery_context={},
        independence_score=0.9,
        now=now,
    )
    assert recent["wallet_discovery_priority_score"] > stale["wallet_discovery_priority_score"]
    assert stale["wallet_discovery_priority_score"] > 0.0



def test_clan_quality_can_break_otherwise_equal_research_priority():
    cfg = ExternalDiscoveryConfig(wallet_priority_cohort_weight=0.20)
    eng = WalletDiscoveryPriorityEngine(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = {
        "rank": None,
        "source_confidence": 0.6,
        "observed_at": now,
    }
    metrics = {
        "smart_capital_30d_score": 0.6,
        "emerging_smart_wallet_score": 0.6,
        "data_quality_score": 0.7,
    }
    plain = eng.score(
        {**row, "wallet_address": "PLAIN"},
        smart_metrics=metrics,
        discovery_context={},
        independence_score=0.9,
        cohort_quality=0.0,
        now=now,
    )
    clan = eng.score(
        {**row, "wallet_address": "CLAN"},
        smart_metrics=metrics,
        discovery_context={},
        independence_score=0.9,
        cohort_quality=0.85,
        now=now,
    )
    assert clan["wallet_discovery_priority_score"] > plain["wallet_discovery_priority_score"]
    assert clan["wallet_discovery_priority_components"]["cohort_quality"] == 0.85



def test_stale_registry_rank_does_not_boost_current_priority():
    cfg = ExternalDiscoveryConfig()
    eng = WalletDiscoveryPriorityEngine(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = {
        "wallet_address": "STALE_TOP",
        "rank": 1,
        "source_confidence": 0.9,
        "observed_at": now - timedelta(hours=2),
    }
    stale = eng.score(
        row,
        smart_metrics={},
        discovery_context={"pump_rank": None, "pump_rank_velocity": 0.0, "pump_rank_acceleration": 0.0},
        independence_score=1.0,
        now=now,
    )
    fresh = eng.score(
        {**row, "observed_at": now},
        smart_metrics={},
        discovery_context={"pump_rank": 1, "pump_rank_velocity": 0.0, "pump_rank_acceleration": 0.0},
        independence_score=1.0,
        now=now,
    )
    assert stale["wallet_discovery_priority_components"]["rank"] == 0.0
    assert fresh["wallet_discovery_priority_components"]["rank"] == 1.0
    assert fresh["wallet_discovery_priority_score"] > stale["wallet_discovery_priority_score"]


def test_future_observed_activity_never_gets_recency_boost():
    cfg = ExternalDiscoveryConfig()
    eng = WalletDiscoveryPriorityEngine(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = eng.score(
        {
            "wallet_address": "FUTURE",
            "rank": None,
            "source_confidence": 0.5,
            "observed_at": now + timedelta(minutes=5),
        },
        smart_metrics={},
        discovery_context={},
        independence_score=1.0,
        now=now,
    )
    assert out["wallet_discovery_priority_components"]["recent_activity"] == 0.0
