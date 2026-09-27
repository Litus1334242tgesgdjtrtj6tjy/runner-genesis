from datetime import datetime, timezone

from runner_genesis.config import Settings
from runner_genesis.db import RuntimeRepository
from runner_genesis.domain.state import WalletBuyObservation
from runner_genesis.ingestion.helius_history import FundingLink
from runner_genesis.orchestrator import RunnerGenesisOmega


def test_persisted_wallet_outcomes_and_funding_graph_hydrate_after_restart(tmp_path):
    db = tmp_path / "research.db"
    url = f"sqlite:///{db}"
    repo = RuntimeRepository(url)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    obs = WalletBuyObservation(
        event_time=t0,
        resolved_at=t0,
        token_mint="OLDMINT",
        buy_eur=100.0,
        realized_return=1.25,
        runner_capture_ratio=0.6,
        hold_seconds=3600,
    )
    repo.record_wallet_outcome("WALLET_A", obs)
    repo.record_funding_relationship(FundingLink(
        wallet="WALLET_A",
        funder="FUNDER_X",
        timestamp=t0,
        sol_amount=2.0,
        signature="SIG",
        confidence=0.95,
    ))

    settings = Settings(database_url=url)
    settings.features["database_persistence"] = {"enabled": True}
    engine = RunnerGenesisOmega(settings)

    history = engine.store.resolved_wallet_history_as_of(
        "WALLET_A", datetime(2026, 1, 2, tzinfo=timezone.utc)
    )
    assert len(history) == 1
    assert history[0].realized_return == 1.25
    assert "FUNDER_X" in engine.actor.wallet_to_funders["WALLET_A"]
