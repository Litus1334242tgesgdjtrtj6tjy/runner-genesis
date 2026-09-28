from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any


@dataclass
class Alert:
    timestamp: datetime
    token_mint: str
    alert_type: str
    severity: str
    message: str
    payload: dict[str, Any]


class AlertEngine:
    """Small in-process deduplicating alert bus used by PAPER/SHADOW."""

    def __init__(self, cooldown_seconds: float = 60.0, max_alerts: int = 5000) -> None:
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.max_alerts = max_alerts
        self.alerts: list[Alert] = []
        self.last_key: dict[tuple[str, str], datetime] = {}
        self.last_persistence: dict[str, float] = {}

    def emit(self, now: datetime, mint: str, alert_type: str, message: str, severity: str = 'INFO', payload: dict[str, Any] | None = None) -> Alert | None:
        key = (mint, alert_type)
        prev = self.last_key.get(key)
        if prev is not None and now - prev < self.cooldown:
            return None
        a = Alert(now, mint, alert_type, severity, message, payload or {})
        self.last_key[key] = now
        self.alerts.append(a)
        if len(self.alerts) > self.max_alerts:
            del self.alerts[: len(self.alerts) - self.max_alerts]
        return a

    def evaluate(self, now: datetime, mint: str, features: dict, action: str, event_wallet: str | None = None) -> list[Alert]:
        emitted: list[Alert] = []
        def add(t, msg, severity='INFO', payload=None):
            a = self.emit(now, mint, t, msg, severity, payload)
            if a: emitted.append(a)

        if event_wallet and float(features.get('wallet_quality', 0.0) or 0.0) >= 0.55:
            add('SMART_WALLET_NEW_ENTRY', 'High-quality wallet activity detected', payload={'wallet': event_wallet})
        if float(features.get('accumulation_score', 0.0) or 0.0) >= 0.60:
            add('SMART_CAPITAL_ACCUMULATION', 'Smart-capital accumulation is elevated')
        if float(features.get('weighted_smart_capital_consensus', 0.0) or 0.0) >= 0.62:
            add('SMART_CAPITAL_CONSENSUS', 'Weighted independent smart-capital consensus is elevated')
        if str(features.get('entry_validity')) == 'ENTRY_TOO_LATE':
            add('ENTRY_TOO_LATE', 'Signal may be valid but executable entry is too extended', 'WARN')
        distribution = float(features.get('distribution_score', 0.0) or 0.0)
        if distribution >= 0.68:
            add('SMART_CAPITAL_DISTRIBUTION', 'Distribution pressure is elevated', 'WARN', {'distribution_score': distribution})
        if action in {'PROTECT', 'PARTIAL_EXIT'}:
            add('PROTECT_POSITION', f'Paper trader action: {action}', 'WARN')
        if action == 'EXIT':
            add('EXIT_CONFIRMED', 'Paper exit action confirmed', 'WARN')
        if str(features.get('signal_validity')) == 'NOT_CONFIRMED' and mint in self.last_persistence:
            add('SIGNAL_INVALIDATED', 'Previously observed setup is no longer confirmed', 'WARN')

        p = float(features.get('runner_persistence', 0.0) or 0.0)
        old = self.last_persistence.get(mint)
        if old is not None:
            if p - old >= 0.15:
                add('PERSISTENCE_RISING', 'Runner persistence rose materially', payload={'previous': old, 'current': p})
            elif old - p >= 0.15:
                add('PERSISTENCE_FALLING', 'Runner persistence fell materially', 'WARN', {'previous': old, 'current': p})
        self.last_persistence[mint] = p

        if float(features.get('top_trader_wave_score', 0.0) or 0.0) >= 0.60:
            add('TOP_TRADER_WAVE', 'Pump top-trader wave context detected', payload={
                'raw_top_traders': features.get('top_trader_count'),
                'effective_top_traders': features.get('top_trader_effective_count'),
                'new_top_traders_60s': features.get('new_top_traders_60s'),
            })
        if (
            float(features.get('cohort_concentration', 0.0) or 0.0) >= 0.60
            and float(features.get('raw_wallet_count', 0.0) or 0.0) >= 3.0
        ):
            add('PUMPFUN_COHORT_FORMING', 'Related wallet cohort activity is forming', 'INFO', {
                'raw_wallets': features.get('raw_wallet_count'),
                'effective_wallets': features.get('effective_wallet_count'),
                'same_funder_concentration': features.get('same_funder_concentration'),
            })
        if float(features.get('kol_wave_score', 0.0) or 0.0) >= 0.60:
            add('KOL_WAVE', 'KOL-discovery wave context detected')
        if float(features.get('fomo_score', 0.0) or 0.0) >= 0.65:
            add('FOMO_ACCELERATION', 'Independent attention/FOMO sources are accelerating')
        if float(features.get('early_formation_score', 0.0) or 0.0) >= 0.55:
            add(
                'EARLY_SMART_CAPITAL_FORMATION',
                'Independent Smart Capital is accelerating before excessive price extension',
                'INFO',
                {
                    'score': features.get('early_formation_score'),
                    'smart_growth': features.get('early_formation_smart_growth'),
                    'entry_headroom': features.get('early_formation_entry_headroom'),
                    'price_return': features.get('early_formation_price_return'),
                },
            )
        if float(features.get('mirofish_collapse_frequency', 0.0) or 0.0) >= 0.60:
            add('MIROFISH_COLLAPSE_RISK_RISING', 'MiroFish simulation collapse frequency is elevated', 'WARN')
        return emitted

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        return [asdict(a) for a in self.alerts[-max(1, limit):]]
