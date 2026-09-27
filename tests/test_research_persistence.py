from datetime import datetime, timezone

from runner_genesis.config import Settings
from runner_genesis.db import RuntimeRepository
from runner_genesis.domain.state import WalletBuyObservation
from runner_genesis.ingestion.helius_history import FundingLink
from runner_genesis.execution import PaperFill
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


def test_persisted_pump_leaderboard_hydrates_after_restart(tmp_path):
    db = tmp_path / "research_leaderboard.db"
    url = f"sqlite:///{db}"
    repo = RuntimeRepository(url)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.record_leaderboard({
        "wallet_address": "TOP_WALLET",
        "source": "PUMPFUN_TOP_TRADER",
        "observed_at": t0,
        "rank": 7,
        "monthly_pnl": 1234.5,
        "username": "tester",
        "source_window": "1M",
        "source_confidence": 0.9,
    })

    settings = Settings(database_url=url)
    settings.features["database_persistence"] = {"enabled": True}
    engine = RunnerGenesisOmega(settings)
    ctx = engine.discovery.wallet_context(
        "TOP_WALLET", t0.replace(minute=30)
    )
    assert ctx["pump_top_trader_present"] == 1.0
    assert ctx["pump_rank"] == 7


def test_persisted_paper_fill_restores_open_position_after_restart(tmp_path):
    db = tmp_path / "paper_restart.db"
    url = f"sqlite:///{db}"
    repo = RuntimeRepository(url)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fill = PaperFill(
        token_mint="MINT",
        side="BUY",
        requested_eur=10.0,
        filled_eur=10.0,
        quantity=10.0,
        reference_price=1.0,
        execution_price=1.0,
        slippage_pct=0.0,
        fees_eur=0.10,
        latency_ms=100.0,
        failed=False,
        partial=False,
        timestamp=t0,
    )
    repo.record_fill(fill)

    settings = Settings(database_url=url, paper_starting_capital_eur=300.0)
    settings.features["database_persistence"] = {"enabled": True}
    engine = RunnerGenesisOmega(settings)
    account = engine.portfolio.account

    assert len(engine.portfolio.fills) == 1
    assert "MINT" in account.positions
    assert abs(account.cash_eur - 289.90) < 1e-9
    assert abs(account.positions["MINT"].quantity - 10.0) < 1e-9


def test_delayed_paper_signal_restores_after_restart(tmp_path):
    db = tmp_path / "pending_restart.db"
    url = f"sqlite:///{db}"
    repo = RuntimeRepository(url)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    due = t0.replace(minute=1)
    repo.record_paper_update(
        "MINT_PENDING",
        t0,
        "PENDING_ENTER",
        {
            "due_time": due,
            "amount_eur": 12.0,
            "fusion_research_score": 0.8,
            "fusion_confidence": 0.7,
            "weighted_smart_capital_consensus": 0.75,
            "top_trader_wave_score": 0.6,
        },
    )

    settings = Settings(database_url=url, paper_starting_capital_eur=300.0)
    settings.features["database_persistence"] = {"enabled": True}
    engine = RunnerGenesisOmega(settings)

    assert "MINT_PENDING" in engine.pending_orders
    pending = engine.pending_orders["MINT_PENDING"]
    assert pending.proposal.amount_eur == 12.0
    assert pending.due_time == due
    assert "RESTORED_DELAYED_PAPER_SIGNAL" in pending.proposal.reasons


def test_persisted_fill_prevents_duplicate_pending_restore(tmp_path):
    db = tmp_path / "pending_filled.db"
    url = f"sqlite:///{db}"
    repo = RuntimeRepository(url)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    due = t0.replace(minute=1)
    repo.record_paper_update(
        "MINT_DONE",
        t0,
        "PENDING_ENTER",
        {"due_time": due, "amount_eur": 10.0},
    )
    repo.record_fill(PaperFill(
        token_mint="MINT_DONE",
        side="BUY",
        requested_eur=10.0,
        filled_eur=10.0,
        quantity=10.0,
        reference_price=1.0,
        execution_price=1.0,
        slippage_pct=0.0,
        fees_eur=0.0,
        latency_ms=10.0,
        failed=False,
        partial=False,
        timestamp=due,
    ))

    settings = Settings(database_url=url, paper_starting_capital_eur=300.0)
    settings.features["database_persistence"] = {"enabled": True}
    engine = RunnerGenesisOmega(settings)

    assert "MINT_DONE" not in engine.pending_orders
    assert "MINT_DONE" in engine.portfolio.account.positions
