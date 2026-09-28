from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

EPS = 1e-12


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _token_identity(engine, mint: str) -> dict[str, Any]:
    token = engine.store.tokens.get(mint)
    meta = dict(getattr(token, "metadata", {}) or {}) if token is not None else {}
    symbol = str(meta.get("token_symbol") or meta.get("symbol") or "").strip()
    name = str(meta.get("token_name") or meta.get("name") or "").strip()
    return {
        "token": mint,
        "symbol": symbol or mint[:6],
        "name": name or symbol or "Solana token",
        "image_url": meta.get("token_image_url") or meta.get("image_url"),
        "dex_url": meta.get("dexscreener_url"),
        "chain": "solana",
    }


def closed_trade_cycles(fills: list[Any]) -> list[dict[str, Any]]:
    """Reconstruct completed PAPER cycles from executable fills with fees."""
    state: dict[str, dict[str, Any]] = {}
    closed: list[dict[str, Any]] = []
    ordered = sorted(fills, key=lambda x: _aware(x.timestamp))

    for fill in ordered:
        if fill.failed or fill.filled_eur <= 0 or fill.quantity <= 0:
            continue
        mint = str(fill.token_mint)
        side = str(fill.side).upper()
        s = state.get(mint)

        if side == "BUY":
            if s is None or float(s["qty"]) <= EPS:
                s = {
                    "qty": 0.0, "cost": 0.0, "invested": 0.0, "proceeds": 0.0,
                    "realized": 0.0, "fees": 0.0, "buy_qty": 0.0, "buy_value": 0.0,
                    "sell_qty": 0.0, "sell_value": 0.0, "opened_at": _aware(fill.timestamp),
                    "fill_count": 0,
                }
                state[mint] = s
            total_cost = float(fill.filled_eur) + float(fill.fees_eur)
            s["qty"] += float(fill.quantity)
            s["cost"] += total_cost
            s["invested"] += total_cost
            s["fees"] += float(fill.fees_eur)
            s["buy_qty"] += float(fill.quantity)
            s["buy_value"] += float(fill.quantity) * float(fill.execution_price)
            s["fill_count"] += 1
            continue

        if side != "SELL" or s is None or float(s["qty"]) <= EPS:
            continue

        before_qty = float(s["qty"])
        sold_qty = min(before_qty, float(fill.quantity))
        if sold_qty <= EPS:
            continue
        avg_cost = float(s["cost"]) / max(before_qty, EPS)
        released_cost = sold_qty * avg_cost
        fee_fraction = sold_qty / max(float(fill.quantity), EPS)
        exit_fee = float(fill.fees_eur) * fee_fraction
        gross = sold_qty * float(fill.execution_price)
        proceeds = gross - exit_fee
        realized = proceeds - released_cost

        s["qty"] = max(0.0, before_qty - sold_qty)
        s["cost"] = max(0.0, float(s["cost"]) - released_cost)
        s["proceeds"] += proceeds
        s["realized"] += realized
        s["fees"] += exit_fee
        s["sell_qty"] += sold_qty
        s["sell_value"] += gross
        s["fill_count"] += 1

        if float(s["qty"]) <= 1e-10:
            invested = max(float(s["invested"]), EPS)
            opened_at = _aware(s["opened_at"])
            closed_at = _aware(fill.timestamp)
            closed.append({
                "token": mint,
                "opened_at": opened_at,
                "closed_at": closed_at,
                "hold_seconds": max(0.0, (closed_at - opened_at).total_seconds()),
                "invested_eur": float(s["invested"]),
                "proceeds_eur": float(s["proceeds"]),
                "realized_pnl_eur": float(s["realized"]),
                "return_pct": float(s["realized"]) / invested,
                "fees_eur": float(s["fees"]),
                "avg_entry_price": float(s["buy_value"]) / max(float(s["buy_qty"]), EPS),
                "avg_exit_price": float(s["sell_value"]) / max(float(s["sell_qty"]), EPS),
                "fill_count": int(s["fill_count"]),
            })
            state.pop(mint, None)

    return closed


def _period_starts(now: datetime, timezone_name: str) -> dict[str, datetime]:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = timezone.utc
    local = _aware(now).astimezone(tz)
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    week = day - timedelta(days=day.weekday())
    month = day.replace(day=1)
    return {
        "day": day.astimezone(timezone.utc),
        "week": week.astimezone(timezone.utc),
        "month": month.astimezone(timezone.utc),
    }


def _equity_change(repository, current_equity: float, start: datetime) -> tuple[float | None, str]:
    if repository is None or not hasattr(repository, "load_equity_snapshot_at_or_before"):
        return None, "UNAVAILABLE"
    row = repository.load_equity_snapshot_at_or_before(start)
    if row is None:
        return None, "NO_BASELINE"
    return current_equity - float(row["equity_eur"]), "EQUITY_SNAPSHOT"


def build_paper_profile(engine, timezone_name: str = "Europe/Madrid", curve_limit: int = 480) -> dict[str, Any]:
    account = engine.portfolio.account
    now = max(
        (t.last_event_at for t in engine.store.tokens.values() if t.last_event_at),
        default=datetime.now(timezone.utc),
    )
    now = _aware(now)
    current_equity = float(account.equity_eur)
    total_pnl = current_equity - float(account.starting_cash_eur)
    unrealized = 0.0
    open_rows: list[dict[str, Any]] = []
    last_decision = {d.token_mint: d for d in engine.decisions}

    for mint, position in account.positions.items():
        token = engine.store.tokens.get(mint)
        current_price = float(
            (token.price_usd if token is not None else None)
            or engine.portfolio.marks.get(mint)
            or position.avg_entry_price
        )
        market_value = float(position.quantity) * current_price
        pnl = market_value - float(position.cost_basis_eur)
        unrealized += pnl
        decision = last_decision.get(mint)
        open_rows.append({
            **_token_identity(engine, mint),
            "quantity": float(position.quantity),
            "avg_entry_price": float(position.avg_entry_price),
            "current_price": current_price,
            "invested_eur": float(position.cost_basis_eur),
            "market_value_eur": market_value,
            "unrealized_pnl_eur": pnl,
            "pnl_pct": pnl / max(float(position.cost_basis_eur), EPS),
            "realized_pnl_eur": float(position.realized_pnl_eur),
            "opened_at": _aware(position.opened_at),
            "hold_seconds": max(0.0, (now - _aware(position.opened_at)).total_seconds()),
            "adds": int(position.adds),
            "action": decision.action if decision is not None else "HOLD",
            "persistence": decision.features.get("runner_persistence") if decision is not None else None,
            "distribution": decision.features.get("distribution_score") if decision is not None else None,
        })
    open_rows.sort(key=lambda x: float(x["market_value_eur"]), reverse=True)

    cycles = closed_trade_cycles(engine.portfolio.fills)
    closed_rows = [{**_token_identity(engine, r["token"]), **r} for r in reversed(cycles)]
    wins = sum(float(x["realized_pnl_eur"]) > 0 for x in cycles)
    win_rate = wins / len(cycles) if cycles else None

    activity = []
    for fill in reversed(engine.portfolio.fills[-200:]):
        activity.append({
            **_token_identity(engine, fill.token_mint),
            "side": fill.side,
            "timestamp": _aware(fill.timestamp),
            "filled_eur": float(fill.filled_eur),
            "quantity": float(fill.quantity),
            "execution_price": float(fill.execution_price),
            "fees_eur": float(fill.fees_eur),
            "failed": bool(fill.failed),
            "partial": bool(fill.partial),
            "reason": fill.reason,
            "proposal_action": fill.proposal_action,
        })

    starts = _period_starts(now, timezone_name)
    period_pnl = {}
    period_source = {}
    for label, start in starts.items():
        value, source = _equity_change(engine.repository, current_equity, start)
        if value is None:
            value = sum(
                float(x["realized_pnl_eur"])
                for x in cycles
                if _aware(x["closed_at"]) >= start
            )
            source = "REALIZED_FALLBACK"
        period_pnl[label] = value
        period_source[label] = source

    curve = []
    if engine.repository is not None and hasattr(engine.repository, "load_equity_snapshots"):
        curve = engine.repository.load_equity_snapshots(limit=max(2, int(curve_limit)))
    if not curve:
        curve = [{"observed_at": now, "equity_eur": current_equity}]

    pending = []
    for mint, order in sorted(engine.pending_orders.items(), key=lambda x: x[1].due_time):
        pending.append({
            **_token_identity(engine, mint),
            "action": order.proposal.action.value,
            "amount_eur": float(order.proposal.amount_eur),
            "signal_time": _aware(order.signal_time),
            "due_time": _aware(order.due_time),
        })

    return {
        "profile": {
            "handle": "@runner.genesis",
            "display_name": "RUNNER GENESIS PAPER",
            "network": "solana",
            "mode": "PAPER",
            "currency": "EUR",
            "timezone": timezone_name,
            "live_trading": False,
        },
        "summary": {
            "starting_balance_eur": float(account.starting_cash_eur),
            "cash_eur": float(account.cash_eur),
            "equity_eur": current_equity,
            "position_value_eur": max(0.0, current_equity - float(account.cash_eur)),
            "total_pnl_eur": total_pnl,
            "total_pnl_pct": total_pnl / max(float(account.starting_cash_eur), EPS),
            "realized_pnl_eur": float(account.realized_pnl_eur),
            "unrealized_pnl_eur": unrealized,
            "day_pnl_eur": period_pnl["day"],
            "week_pnl_eur": period_pnl["week"],
            "month_pnl_eur": period_pnl["month"],
            "period_sources": period_source,
            "open_positions": len(open_rows),
            "closed_positions": len(closed_rows),
            "win_rate": win_rate,
            "wins": wins,
            "losses": len(cycles) - wins,
            "fees_eur": sum(float(f.fees_eur) for f in engine.portfolio.fills),
            "updated_at": now,
        },
        "open_positions": open_rows,
        "closed_positions": closed_rows[:500],
        "activity": activity,
        "pending_orders": pending,
        "equity_curve": curve,
    }
