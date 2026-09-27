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
