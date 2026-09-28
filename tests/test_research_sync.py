import pytest
from datetime import datetime, timezone
from types import SimpleNamespace

from runner_genesis.config import Settings, PumpDiscoveryConfig
from runner_genesis.engines.discovery import PumpDiscoveryEngine
from runner_genesis.research_sync import ResearchSyncCoordinator


def test_research_sync_can_run_helius_only_for_seeded_wallets():
    settings = Settings(helius_api_key="test-key")
    settings.external_discovery.fomoscan_enabled = False
    discovery = PumpDiscoveryEngine(PumpDiscoveryConfig())
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    discovery.ingest_leaderboard(
        [{"wallet_address": "W1", "rank": 3, "monthly_pnl": 500}],
        observed_at=t0,
        source="PUMPFUN_TOP_TRADER",
    )
    engine = SimpleNamespace(discovery=discovery)
    coordinator = ResearchSyncCoordinator(settings, engine)
    assert coordinator.enabled is True
    rows = coordinator._seed_rows_from_registry()
    assert len(rows) == 1
    assert rows[0]["wallet_address"] == "W1"
    assert rows[0]["rank"] == 3


def test_research_sync_waits_when_no_provider_keys_exist():
    settings = Settings()
    settings.helius_api_key = None
    settings.fomoscan_api_key = None
    settings.external_discovery.fomoscan_enabled = True
    engine = SimpleNamespace(discovery=PumpDiscoveryEngine(PumpDiscoveryConfig()))
    coordinator = ResearchSyncCoordinator(settings, engine)
    assert coordinator.enabled is False



def test_live_onchain_wallet_enters_helius_qualification_queue():
    settings = Settings(helius_api_key="test-key")
    settings.external_discovery.fomoscan_enabled = False
    discovery = PumpDiscoveryEngine(PumpDiscoveryConfig())
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    wallet_state = SimpleNamespace(first_seen=t0, last_seen=t0)
    engine = SimpleNamespace(
        discovery=discovery,
        store=SimpleNamespace(wallets={"LIVE_WALLET": wallet_state}),
    )
    coordinator = ResearchSyncCoordinator(settings, engine)
    rows = coordinator._seed_rows_from_registry()
    assert len(rows) == 1
    assert rows[0]["wallet_address"] == "LIVE_WALLET"
    assert rows[0]["rank"] is None
    assert rows[0]["discovery_kind"] == "LIVE_ONCHAIN_CANDIDATE"



class _FakeSmart:
    def emerging_wallet_metrics(self, wallet, now, store):
        if wallet == "EMERGING":
            return {
                "smart_capital_30d_score": 0.90,
                "emerging_smart_wallet_score": 0.85,
                "data_quality_score": 0.85,
                "sample_size_30d": 18,
            }
        return {
            "smart_capital_30d_score": 0.0,
            "emerging_smart_wallet_score": 0.0,
            "data_quality_score": 0.0,
            "sample_size_30d": 0,
        }


class _FakeActor:
    def independence_factor(self, wallet, peers):
        return 0.95


def test_dynamic_priority_can_choose_strong_emerging_over_weak_ranked_wallet():
    settings = Settings(helius_api_key="test-key")
    settings.external_discovery.wallet_priority_enabled = True
    settings.external_discovery.wallet_priority_candidate_pool = 10
    discovery = PumpDiscoveryEngine(PumpDiscoveryConfig())
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    discovery.ingest_leaderboard(
        [{"wallet_address": "TOP", "rank": 50, "monthly_pnl": 100}],
        observed_at=now,
        source="PUMPFUN_TOP_TRADER",
    )
    engine = SimpleNamespace(
        discovery=discovery,
        smart=_FakeSmart(),
        actor=_FakeActor(),
        store=SimpleNamespace(wallets={}),
    )
    coordinator = ResearchSyncCoordinator(settings, engine)
    selected = coordinator._priority_select(
        {
            "TOP": {
                "wallet_address": "TOP",
                "rank": 50,
                "source_confidence": 0.9,
                "observed_at": now,
            },
            "EMERGING": {
                "wallet_address": "EMERGING",
                "rank": None,
                "source_confidence": 0.55,
                "observed_at": now,
            },
        },
        limit=1,
        now=now,
    )
    assert selected[0]["wallet_address"] == "EMERGING"
    assert selected[0]["wallet_discovery_priority_score"] > 0



class _BrokenFomoProvider:
    def __init__(self, *args, **kwargs):
        pass

    async def pump_leaderboard(self):
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_fomoscan_failure_falls_back_to_registry_without_stopping_research(monkeypatch):
    settings = Settings(fomoscan_api_key="test-key")
    settings.helius_history.enabled = False
    settings.external_discovery.fomoscan_enabled = True
    settings.external_discovery.wallet_priority_enabled = False
    discovery = PumpDiscoveryEngine(PumpDiscoveryConfig())
    now = datetime.now(timezone.utc)
    discovery.ingest_leaderboard(
        [{"wallet_address": "W1", "rank": 4, "monthly_pnl": 500}],
        observed_at=now,
        source="PUMPFUN_TOP_TRADER",
    )
    engine = SimpleNamespace(
        discovery=discovery,
        repository=None,
        store=SimpleNamespace(wallets={}),
    )
    monkeypatch.setattr(
        "runner_genesis.research_sync.FomoScanPumpProvider",
        _BrokenFomoProvider,
    )
    coordinator = ResearchSyncCoordinator(settings, engine)
    result = await coordinator.sync_once(max_wallets=1)
    assert result["status"] == "OK"
    assert result["discovery_source"] == "FOMOSCAN_ERROR_FALLBACK_REGISTRY"
    assert result["external_discovery_error"]["error"] == "RuntimeError"
    assert result["selected_for_backfill"] == 1
