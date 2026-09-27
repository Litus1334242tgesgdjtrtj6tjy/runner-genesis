from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, mean, pstdev
import uuid

from .orchestrator import RunnerGenesisOmega
from .ingestion.replay import ReplaySource


@dataclass
class BacktestMetrics:
    events: int
    decisions: int
    fills: int
    failed_fills: int
    ending_equity_eur: float
    net_pnl_eur: float
    roi: float
    max_drawdown_pct: float
    closed_trade_count: int = 0
    win_rate: float | None = None
    average_return: float | None = None
    median_return: float | None = None
    expectancy_eur: float | None = None
    profit_factor: float | None = None
    fees_eur: float = 0.0
    turnover_eur: float = 0.0
    partial_fill_rate: float = 0.0
    entry_too_late_count: int = 0
    risk_reject_count: int = 0
    pending_invalidated_count: int = 0
    failure_rate: float = 0.0
    average_hold_seconds: float | None = None
    median_hold_seconds: float | None = None
    average_mfe: float | None = None
    median_mfe: float | None = None
    average_mae: float | None = None
    median_mae: float | None = None
    captured_mfe_ratio: float | None = None
    pct_2x: float | None = None
    pct_3x: float | None = None
    pct_5x: float | None = None
    pct_10x: float | None = None
    sharpe_like: float | None = None
    fee_to_turnover_pct: float = 0.0


def _closed_trade_details(fills) -> list[dict]:
    """Reconstruct fully closed PAPER cycles from executable fills."""
    state: dict[str, dict[str, float | datetime]] = {}
    closed: list[dict] = []
    for fill in sorted(fills, key=lambda x: x.timestamp):
        if fill.failed or fill.filled_eur <= 0 or fill.quantity <= 0:
            continue
        s = state.setdefault(
            fill.token_mint,
            {
                "qty": 0.0,
                "cost": 0.0,
                "cycle_cost": 0.0,
                "realized": 0.0,
                "opened_at": fill.timestamp,
            },
        )
        if fill.side == "BUY":
            if float(s["qty"]) <= 1e-12:
                s["opened_at"] = fill.timestamp
            total_cost = float(fill.filled_eur) + float(fill.fees_eur)
            s["qty"] = float(s["qty"]) + float(fill.quantity)
            s["cost"] = float(s["cost"]) + total_cost
            s["cycle_cost"] = float(s["cycle_cost"]) + total_cost
            continue
        if fill.side != "SELL" or float(s["qty"]) <= 0:
            continue
        qty = min(float(s["qty"]), float(fill.quantity))
        avg_cost = float(s["cost"]) / max(float(s["qty"]), 1e-12)
        released = qty * avg_cost
        ratio = qty / max(float(fill.quantity), 1e-12)
        proceeds = qty * float(fill.execution_price) - float(fill.fees_eur) * ratio
        pnl = proceeds - released
        s["realized"] = float(s["realized"]) + pnl
        s["qty"] = float(s["qty"]) - qty
        s["cost"] = max(0.0, float(s["cost"]) - released)
        if float(s["qty"]) <= 1e-10:
            cycle_cost = max(float(s["cycle_cost"]), 1e-12)
            opened_at = s["opened_at"]
            closed.append({
                "token_mint": fill.token_mint,
                "return_fraction": float(s["realized"]) / cycle_cost,
                "realized_pnl_eur": float(s["realized"]),
                "opened_at": opened_at,
                "closed_at": fill.timestamp,
                "hold_seconds": max(
                    0.0,
                    (fill.timestamp - opened_at).total_seconds(),
                ) if isinstance(opened_at, datetime) else None,
            })
            state[fill.token_mint] = {
                "qty": 0.0,
                "cost": 0.0,
                "cycle_cost": 0.0,
                "realized": 0.0,
                "opened_at": fill.timestamp,
            }
    return closed


def _closed_trade_results(fills) -> list[tuple[float, float]]:
    """Backward-compatible compact view of closed PAPER cycles."""
    return [
        (float(x["return_fraction"]), float(x["realized_pnl_eur"]))
        for x in _closed_trade_details(fills)
    ]


class Backtester:
    def __init__(self, engine: RunnerGenesisOmega):
        self.engine = engine

    def run(self, path: str, variant: str = "FULL") -> BacktestMetrics:
        events = 0
        max_dd = 0.0
        for e in ReplaySource(path).events():
            events += 1
            self.engine.process(e)
            a = self.engine.portfolio.account
            dd = (a.peak_equity_eur - a.equity_eur) / max(a.peak_equity_eur, 1e-9)
            max_dd = max(max_dd, dd)

        a = self.engine.portfolio.account
        fills = self.engine.portfolio.fills
        pnl = a.equity_eur - a.starting_cash_eur
        closed = _closed_trade_results(fills)
        returns = [r for r, _ in closed]
        realized = [p for _, p in closed]
        gains = sum(x for x in realized if x > 0)
        losses = abs(sum(x for x in realized if x < 0))
        nonfailed = [f for f in fills if not f.failed]
        partial = [f for f in nonfailed if f.partial]
        decisions = self.engine.decisions

        metrics = BacktestMetrics(
            events=events,
            decisions=len(decisions),
            fills=len(fills),
            failed_fills=sum(bool(f.failed) for f in fills),
            ending_equity_eur=a.equity_eur,
            net_pnl_eur=pnl,
            roi=pnl / max(a.starting_cash_eur, 1e-9),
            max_drawdown_pct=max_dd,
            closed_trade_count=len(closed),
            win_rate=(sum(r > 0 for r in returns) / len(returns)) if returns else None,
            average_return=(sum(returns) / len(returns)) if returns else None,
            median_return=median(returns) if returns else None,
            expectancy_eur=(sum(realized) / len(realized)) if realized else None,
            profit_factor=(gains / losses) if losses > 0 else (None if gains <= 0 else float("inf")),
            fees_eur=sum(float(f.fees_eur) for f in fills),
            turnover_eur=sum(float(f.filled_eur) for f in fills),
            partial_fill_rate=(len(partial) / len(nonfailed)) if nonfailed else 0.0,
            entry_too_late_count=sum(str(d.features.get("entry_validity")) == "ENTRY_TOO_LATE" for d in decisions),
            risk_reject_count=sum(d.action == "RISK_REJECT" for d in decisions),
            pending_invalidated_count=sum("PENDING_SIGNAL_INVALIDATED" in d.risks for d in decisions),
        )

        if self.engine.repository:
            run_id = uuid.uuid4().hex
            created = datetime.now(timezone.utc)
            payload = asdict(metrics)
            self.engine.repository.record_backtest_run(
                run_id,
                created,
                variant,
                payload,
                dataset_id=str(Path(path)),
            )
            self.engine.repository.record_backtest_metrics(run_id, payload)
        return metrics
