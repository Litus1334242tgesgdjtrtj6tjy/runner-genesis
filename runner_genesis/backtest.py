from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, mean, pstdev
import uuid
from math import sqrt

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
        open_paths: dict[str, dict] = {}
        closed_paths: list[dict] = []

        def update_path(mint: str, timestamp: datetime, price: float | None) -> None:
            tracker = open_paths.get(mint)
            if tracker is None or price is None or float(price) <= 0:
                return
            ret = float(price) / max(float(tracker["entry_price"]), 1e-12) - 1.0
            tracker["mfe"] = max(float(tracker["mfe"]), ret)
            tracker["mae"] = min(float(tracker["mae"]), ret)
            tracker["last_mark_at"] = timestamp

        for e in ReplaySource(path).events():
            events += 1
            update_path(e.token_mint, e.timestamp, e.price_usd)

            fill_count_before = len(self.engine.portfolio.fills)
            self.engine.process(e)
            new_fills = self.engine.portfolio.fills[fill_count_before:]

            for fill in new_fills:
                if fill.failed or fill.filled_eur <= 0 or fill.quantity <= 0:
                    continue
                if fill.side == "BUY" and fill.token_mint not in open_paths:
                    open_paths[fill.token_mint] = {
                        "token_mint": fill.token_mint,
                        "opened_at": fill.timestamp,
                        "entry_price": float(fill.execution_price),
                        "mfe": 0.0,
                        "mae": 0.0,
                        "last_mark_at": fill.timestamp,
                    }

            update_path(e.token_mint, e.timestamp, e.price_usd)

            # A cycle is path-complete when the executable PAPER position is fully gone.
            if e.token_mint in open_paths and e.token_mint not in self.engine.portfolio.account.positions:
                tracker = open_paths.pop(e.token_mint)
                tracker["closed_at"] = max(
                    (
                        fill.timestamp
                        for fill in new_fills
                        if fill.token_mint == e.token_mint and fill.side == "SELL" and not fill.failed
                    ),
                    default=e.timestamp,
                )
                closed_paths.append(tracker)

            a = self.engine.portfolio.account
            dd = (a.peak_equity_eur - a.equity_eur) / max(a.peak_equity_eur, 1e-9)
            max_dd = max(max_dd, dd)

        a = self.engine.portfolio.account
        fills = self.engine.portfolio.fills
        pnl = a.equity_eur - a.starting_cash_eur
        closed_details = _closed_trade_details(fills)
        returns = [float(x["return_fraction"]) for x in closed_details]
        realized = [float(x["realized_pnl_eur"]) for x in closed_details]
        hold_times = [
            float(x["hold_seconds"])
            for x in closed_details
            if x.get("hold_seconds") is not None
        ]
        gains = sum(x for x in realized if x > 0)
        losses = abs(sum(x for x in realized if x < 0))
        nonfailed = [f for f in fills if not f.failed]
        partial = [f for f in nonfailed if f.partial]
        decisions = self.engine.decisions
        failed_count = sum(bool(f.failed) for f in fills)
        turnover = sum(float(f.filled_eur) for f in fills)
        fees = sum(float(f.fees_eur) for f in fills)

        # Match closed path extrema to closed executable cycles by token and sequence.
        path_queues: dict[str, list[dict]] = defaultdict(list)
        for path_row in sorted(closed_paths, key=lambda x: x["closed_at"]):
            path_queues[str(path_row["token_mint"])].append(path_row)
        mfe_values: list[float] = []
        mae_values: list[float] = []
        captured_values: list[float] = []
        for detail in closed_details:
            queue = path_queues.get(str(detail["token_mint"]), [])
            if not queue:
                continue
            path_row = queue.pop(0)
            mfe = float(path_row["mfe"])
            mae = float(path_row["mae"])
            mfe_values.append(mfe)
            mae_values.append(mae)
            if mfe > 1e-12:
                captured_values.append(float(detail["return_fraction"]) / mfe)

        sharpe_like = None
        if len(returns) >= 2:
            sigma = pstdev(returns)
            if sigma > 1e-12:
                sharpe_like = mean(returns) / sigma * sqrt(len(returns))

        def hit_rate(threshold: float) -> float | None:
            return (
                sum(r >= threshold for r in returns) / len(returns)
                if returns else None
            )

        metrics = BacktestMetrics(
            events=events,
            decisions=len(decisions),
            fills=len(fills),
            failed_fills=failed_count,
            ending_equity_eur=a.equity_eur,
            net_pnl_eur=pnl,
            roi=pnl / max(a.starting_cash_eur, 1e-9),
            max_drawdown_pct=max_dd,
            closed_trade_count=len(closed_details),
            win_rate=(sum(r > 0 for r in returns) / len(returns)) if returns else None,
            average_return=mean(returns) if returns else None,
            median_return=median(returns) if returns else None,
            expectancy_eur=mean(realized) if realized else None,
            profit_factor=(gains / losses) if losses > 0 else (None if gains <= 0 else float("inf")),
            fees_eur=fees,
            turnover_eur=turnover,
            partial_fill_rate=(len(partial) / len(nonfailed)) if nonfailed else 0.0,
            entry_too_late_count=sum(str(d.features.get("entry_validity")) == "ENTRY_TOO_LATE" for d in decisions),
            risk_reject_count=sum(d.action == "RISK_REJECT" for d in decisions),
            pending_invalidated_count=sum("PENDING_SIGNAL_INVALIDATED" in d.risks for d in decisions),
            failure_rate=(failed_count / len(fills)) if fills else 0.0,
            average_hold_seconds=mean(hold_times) if hold_times else None,
            median_hold_seconds=median(hold_times) if hold_times else None,
            average_mfe=mean(mfe_values) if mfe_values else None,
            median_mfe=median(mfe_values) if mfe_values else None,
            average_mae=mean(mae_values) if mae_values else None,
            median_mae=median(mae_values) if mae_values else None,
            captured_mfe_ratio=mean(captured_values) if captured_values else None,
            pct_2x=hit_rate(1.0),
            pct_3x=hit_rate(2.0),
            pct_5x=hit_rate(4.0),
            pct_10x=hit_rate(9.0),
            sharpe_like=sharpe_like,
            fee_to_turnover_pct=(fees / turnover) if turnover > 0 else 0.0,
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

