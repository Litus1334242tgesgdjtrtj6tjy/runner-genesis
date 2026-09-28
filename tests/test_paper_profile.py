from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from runner_genesis.db import RuntimeRepository
from runner_genesis.domain.state import PaperAccount
from runner_genesis.execution import PaperFill
from runner_genesis.paper_profile import build_paper_profile, closed_trade_cycles
from runner_genesis.portfolio import PortfolioLedger
from runner_genesis.state_store import MarketStateStore


T0 = datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc)


def fill(side, eur, qty, price, fee, at):
    return PaperFill(
        token_mint="MINT",
        side=side,
        requested_eur=eur,
        filled_eur=eur,
        quantity=qty,
        reference_price=price,
        execution_price=price,
        slippage_pct=0.0,
        fees_eur=fee,
        latency_ms=0.0,
        failed=False,
        partial=False,
        timestamp=at,
    )


def test_closed_cycles_include_entry_and_exit_fees():
    rows = closed_trade_cycles([
        fill("BUY", 10.0, 10.0, 1.0, 0.10, T0),
        fill("SELL", 12.0, 10.0, 1.2, 0.10, T0 + timedelta(minutes=5)),
    ])
    assert len(rows) == 1
    row = rows[0]
    assert abs(row["realized_pnl_eur"] - 1.80) < 1e-9
    assert abs(row["return_pct"] - (1.80 / 10.10)) < 1e-9
    assert abs(row["fees_eur"] - 0.20) < 1e-9


def test_profile_starts_at_300_and_uses_token_identity():
    ledger = PortfolioLedger(300.0)
    ledger.apply_fill(fill("BUY", 10.0, 10.0, 1.0, 0.10, T0))
    ledger.mark_to_market({"MINT": 1.2})

    store = MarketStateStore()
    token = store.token("MINT")
    token.last_event_at = T0
    token.price_usd = 1.2
    token.metadata.update({
        "token_name": "Demo Coin",
        "token_symbol": "DEMO",
        "token_image_url": "https://example.com/demo.png",
    })
    engine = SimpleNamespace(
        portfolio=ledger,
        store=store,
        decisions=[],
        repository=None,
        pending_orders={},
    )

    profile = build_paper_profile(engine)
    assert profile["profile"]["network"] == "solana"
    assert profile["summary"]["starting_balance_eur"] == 300.0
    assert abs(profile["summary"]["equity_eur"] - 301.9) < 1e-9
    assert len(profile["open_positions"]) == 1
    assert profile["open_positions"][0]["symbol"] == "DEMO"
    assert profile["open_positions"][0]["image_url"].endswith("demo.png")


def test_equity_snapshots_support_period_baselines(tmp_path):
    repo = RuntimeRepository(f"sqlite:///{tmp_path / 'paper.db'}")
    account = PaperAccount(300.0, 300.0)
    repo.record_equity_snapshot(T0, account, {})
    account.equity_eur = 315.0
    account.cash_eur = 315.0
    account.realized_pnl_eur = 15.0
    repo.record_equity_snapshot(T0 + timedelta(hours=1), account, {})

    baseline = repo.load_equity_snapshot_at_or_before(T0 + timedelta(minutes=30))
    assert baseline is not None
    assert baseline["equity_eur"] == 300.0
    assert repo.load_first_equity_snapshot()["equity_eur"] == 300.0
    curve = repo.load_equity_snapshots(limit=10)
    assert [row["equity_eur"] for row in curve] == [300.0, 315.0]
