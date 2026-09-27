from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
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


def _closed_trade_results(fills) -> list[tuple[float, float]]:
    """Return (return_fraction, realized_pnl_eur) for fully closed PAPER cycles."""
    state: dict[str, dict[str, float]] = {}
    closed: list[tuple[float, float]] = []
    for fill in sorted(fills, key=lambda x: x.timestamp):
        if fill.failed or fill.filled_eur <= 0 or fill.quantity <= 0:
            continue
        s = state.setdefault(fill.token_mint, {"qty": 0.0, "cost": 0.0, "cycle_cost": 0.0, "realized": 0.0})
        if fill.side == "BUY":
            total_cost = float(fill.filled_eur) + float(fill.fees_eur)
            s["qty"] += float(fill.quantity)
            s["cost"] += total_cost
            s["cycle_cost"] += total_cost
            continue
        if fill.side != "SELL" or s["qty"] <= 0:
            continue
        qty = min(s["qty"], float(fill.quantity))
        avg_cost = s["cost"] / max(s["qty"], 1e-12)
        released = qty * avg_cost
        # Allocate the sell fee proportionally if a simulated fill exceeds remaining qty.
        ratio = qty / max(float(fill.quantity), 1e-12)
        proceeds = qty * float(fill.execution_price) - float(fill.fees_eur) * ratio
        pnl = proceeds - released
        s["realized"] += pnl
        s["qty"] -= qty
        s["cost"] = max(0.0, s["cost"] - released)
        if s["qty"] <= 1e-10:
            cycle_cost = max(s["cycle_cost"], 1e-12)
            closed.append((s["realized"] / cycle_cost, s["realized"]))
            state[fill.token_mint] = {"qty": 0.0, "cost": 0.0, "cycle_cost": 0.0, "realized": 0.0}
    return closed


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
