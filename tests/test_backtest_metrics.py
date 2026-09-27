from datetime import datetime, timezone, timedelta

from runner_genesis.backtest import _closed_trade_results
from runner_genesis.execution import PaperFill


def fill(side, eur, qty, price, fee, ts):
    return PaperFill(
        token_mint="M",
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
        timestamp=ts,
    )


def test_closed_trade_result_includes_entry_and_exit_fees():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fills = [
        fill("BUY", 100.0, 100.0, 1.0, 1.0, t0),
        fill("SELL", 200.0, 100.0, 2.0, 1.0, t0 + timedelta(minutes=10)),
    ]
    results = _closed_trade_results(fills)
    assert len(results) == 1
    ret, pnl = results[0]
    assert abs(pnl - 98.0) < 1e-9
    assert abs(ret - (98.0 / 101.0)) < 1e-9


def test_open_cycle_is_not_counted_as_closed_trade():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    results = _closed_trade_results([fill("BUY", 100.0, 100.0, 1.0, 1.0, t0)])
    assert results == []
