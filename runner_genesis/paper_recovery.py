from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _aware(value: datetime | str | None) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def recover_pending_specs(
    updates: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    default_delay_seconds: float,
) -> list[dict[str, Any]]:
    """Return durable delayed-PAPER signals that still require a future execution check.

    The DB update log is authoritative when it contains a later terminal update. A fill
    written after a pending signal is an additional crash-safety guard for the small
    window between persisting a fill and persisting its terminal paper-update row.
    """
    latest: dict[str, dict[str, Any]] = {}
    for row in updates:
        mint = str(row.get("token_mint") or "")
        if not mint:
            continue
        observed = _aware(row.get("observed_at"))
        if observed is None:
            continue
        current = latest.get(mint)
        current_time = _aware(current.get("observed_at")) if current else None
        if current_time is None or observed >= current_time:
            latest[mint] = {**row, "observed_at": observed}

    fill_times: dict[str, list[datetime]] = {}
    for row in fills:
        mint = str(row.get("token_mint") or "")
        ts = _aware(row.get("timestamp"))
        if mint and ts is not None:
            fill_times.setdefault(mint, []).append(ts)

    recovered: list[dict[str, Any]] = []
    for mint, row in latest.items():
        update_type = str(row.get("update_type") or "")
        if update_type not in {"PENDING_ENTER", "PENDING_ADD"}:
            continue
        signal_time = _aware(row.get("observed_at"))
        if signal_time is None:
            continue
        if any(ts >= signal_time for ts in fill_times.get(mint, ())):
            continue

        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        due_time = _aware(payload.get("due_time"))
        if due_time is None:
            due_time = signal_time + timedelta(seconds=max(0.0, float(default_delay_seconds)))

        recovered.append({
            "token_mint": mint,
            "action": "ENTER" if update_type == "PENDING_ENTER" else "ADD",
            "signal_time": signal_time,
            "due_time": due_time,
            "amount_eur": float(payload.get("amount_eur") or 0.0),
            "confidence": float(payload.get("fusion_confidence") or 0.0),
            "signal_features": {
                "fusion_research_score": payload.get("fusion_research_score"),
                "fusion_confidence": payload.get("fusion_confidence"),
                "weighted_smart_capital_consensus": payload.get("weighted_smart_capital_consensus"),
                "top_trader_wave_score": payload.get("top_trader_wave_score"),
                "dominant_actor_cluster_id": payload.get("dominant_actor_cluster_id"),
                "dominant_actor_cluster_fraction": payload.get("dominant_actor_cluster_fraction"),
            },
        })
    recovered.sort(key=lambda x: (x["due_time"], x["token_mint"]))
    return recovered
