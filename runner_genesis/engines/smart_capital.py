from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import math
import numpy as np
from ..domain.events import MarketEvent, EventType
from .wallet_quality import WalletQualityEngine

@dataclass
class WalletTokenPosition:
    wallet: str
    token_mint: str
    first_entry_time: datetime | None = None
    last_entry_time: datetime | None = None
    last_activity_time: datetime | None = None
    total_bought_token: float = 0.0
    total_sold_token: float = 0.0
    invested_usd: float = 0.0
    proceeds_usd: float = 0.0
    current_balance_token: float = 0.0
    weighted_entry_value: float = 0.0
    adds: int = 0
    reductions: int = 0
    state: str = "UNKNOWN"
    buy_sizes_usd: list[float] = field(default_factory=list)
    buy_times: list[datetime] = field(default_factory=list)

    @property
    def average_entry_price(self) -> float | None:
        return self.weighted_entry_value / self.total_bought_token if self.total_bought_token > 0 else None

    def apply(self, e: MarketEvent) -> None:
        self.last_activity_time = e.timestamp
        if e.event_type in (EventType.BUY, EventType.DEV_BUY, EventType.RUNNER_HOLDER_ENTRY, EventType.RUNNER_HOLDER_ADD):
            qty = float(e.amount_token or 0.0)
            usd = float(e.usd_value or 0.0)
            px = float(e.price_usd or (usd / qty if qty > 0 else 0.0))
            if self.first_entry_time is None:
                self.first_entry_time = e.timestamp
                self.state = "NEW_POSITION"
            else:
                self.adds += 1
                self.state = "ADD"
            self.last_entry_time = e.timestamp
            self.total_bought_token += qty
            self.current_balance_token += qty
            self.invested_usd += usd
            self.weighted_entry_value += qty * px
            self.buy_sizes_usd.append(usd)
            self.buy_times.append(e.timestamp)
        elif e.event_type in (EventType.SELL, EventType.DEV_SELL, EventType.RUNNER_HOLDER_REDUCE, EventType.RUNNER_HOLDER_EXIT):
            qty = max(0.0, float(e.amount_token or 0.0))
            usd = max(0.0, float(e.usd_value or 0.0))
            self.total_sold_token += qty
            self.current_balance_token = max(0.0, self.current_balance_token - qty)
            self.proceeds_usd += usd
            self.reductions += 1
            self.state = "EXIT" if self.current_balance_token <= 1e-12 else "REDUCE"
        elif self.current_balance_token > 0:
            self.state = "HOLD"

    def held_fraction(self) -> float:
        return max(0.0, min(1.0, self.current_balance_token / max(self.total_bought_token, 1e-12)))

class PositionReconstructor:
    def __init__(self) -> None:
        self.positions: dict[tuple[str, str], WalletTokenPosition] = {}

    def observe(self, e: MarketEvent) -> WalletTokenPosition | None:
        if not e.wallet:
            return None
        if e.event_type not in {
            EventType.BUY, EventType.SELL, EventType.DEV_BUY, EventType.DEV_SELL,
            EventType.RUNNER_HOLDER_ENTRY, EventType.RUNNER_HOLDER_ADD,
            EventType.RUNNER_HOLDER_REDUCE, EventType.RUNNER_HOLDER_EXIT,
        }:
            return self.positions.get((e.wallet, e.token_mint))
        key = (e.wallet, e.token_mint)
        pos = self.positions.setdefault(key, WalletTokenPosition(e.wallet, e.token_mint))
        pos.apply(e)
        return pos

    def token_positions(self, mint: str) -> list[WalletTokenPosition]:
        return [p for (_, m), p in self.positions.items() if m == mint]

class WalletStyleClassifier:
    def classify(self, positions: list[WalletTokenPosition], as_of: datetime) -> tuple[str, float, float, float]:
        if not positions:
            return "UNKNOWN", 0.0, 0.0, 0.0
        holds = []
        retained = []
        for p in positions:
            if p.first_entry_time:
                end = p.last_activity_time or as_of
                holds.append(max(0.0, (end - p.first_entry_time).total_seconds()))
            retained.append(p.held_fraction())
        med_hold = float(np.median(holds)) if holds else 0.0
        med_ret = float(np.median(retained)) if retained else 0.0
        swing = max(0.0, min(1.0, med_hold / (6 * 3600))) * (0.4 + 0.6 * med_ret)
        hold = max(0.0, min(1.0, med_hold / (24 * 3600))) * (0.5 + 0.5 * med_ret)
        if med_hold < 300 and med_ret < 0.35:
            style = "SCALPER"
        elif hold >= 0.55:
            style = "HOLDER"
        elif swing >= 0.45:
            style = "SWING"
        elif med_ret >= 0.5:
            style = "RUNNER"
        else:
            style = "MIXED"
        return style, swing, hold, med_hold

class SmartCapitalEngine:
    def __init__(self, wallet_quality: WalletQualityEngine, actor_graph, cfg: dict | None = None) -> None:
        self.wallet_quality = wallet_quality
        self.actor_graph = actor_graph
        self.cfg = cfg or {}
        self.positions = PositionReconstructor()
        self.style = WalletStyleClassifier()
        self.token_states: dict[str, dict] = {}

    @staticmethod
    def _conviction(pos: WalletTokenPosition) -> tuple[float, float]:
        if not pos.buy_sizes_usd:
            return 0.0, 0.0
        current = pos.buy_sizes_usd[-1]
        median = float(np.median(pos.buy_sizes_usd)) or current or 1.0
        size_ratio = current / max(median, 1e-9)
        score = max(0.0, min(1.0, 0.5 + 0.25 * math.tanh(size_ratio - 1.0)))
        confidence = min(1.0, len(pos.buy_sizes_usd) / 4.0)
        return score, confidence

    @staticmethod
    def _accumulation(pos: WalletTokenPosition) -> float:
        if pos.total_bought_token <= 0:
            return 0.0
        add_component = min(1.0, pos.adds / 3.0)
        retention = pos.held_fraction()
        progression = 0.5
        if len(pos.buy_sizes_usd) >= 2:
            progression = 1.0 if pos.buy_sizes_usd[-1] >= pos.buy_sizes_usd[0] else 0.25
        reduction_penalty = min(1.0, pos.reductions / 2.0)
        return max(0.0, min(1.0, 0.35 * add_component + 0.45 * retention + 0.20 * progression - 0.35 * reduction_penalty))

    def observe_and_features(self, e: MarketEvent, store) -> dict[str, float | str | None]:
        self.positions.observe(e)
        positions = self.positions.token_positions(e.token_mint)
        contributions = []; accumulations = []; convictions = []; qualities = []; swings = []; holds = []; qualified_wallets = []
        total_capital = 0.0
        for p in positions:
            q = self.wallet_quality.compute(p.wallet, e.timestamp, store)
            wallet_positions = [x for (w, _), x in self.positions.positions.items() if w == p.wallet]
            style, swing, hold, _ = self.style.classify(wallet_positions, e.timestamp)
            conviction, _ = self._conviction(p)
            accumulation = self._accumulation(p)
            freshness = 1.0
            if p.last_activity_time:
                age = max(0.0, (e.timestamp - p.last_activity_time).total_seconds())
                freshness = math.exp(-age / max(float(self.cfg.get("freshness_half_life_seconds", 3600.0)), 1.0))
            strategy_match = max(swing, hold, 0.25 if style == "RUNNER" else 0.0)
            quality = float(q.quality)
            contribution = quality * max(strategy_match, 0.15) * max(conviction, 0.25) * freshness
            if p.current_balance_token > 0:
                qualified_wallets.append(p.wallet); contributions.append(contribution); accumulations.append(accumulation); convictions.append(conviction); qualities.append(quality); swings.append(swing); holds.append(hold)
                total_capital += max(0.0, p.invested_usd - p.proceeds_usd)

        eff = self.actor_graph.effective_wallet_count(qualified_wallets)
        raw = len(set(qualified_wallets))
        independence = eff / raw if raw else 0.0
        base = float(np.mean(contributions)) if contributions else 0.0
        breadth = min(1.0, eff / max(float(self.cfg.get("target_effective_wallets", 3.0)), 1.0))
        consensus = max(0.0, min(1.0, base * 0.65 + breadth * 0.35))
        accumulation = float(np.mean(accumulations)) if accumulations else 0.0
        conviction = float(np.mean(convictions)) if convictions else 0.0
        quality = float(np.mean(qualities)) if qualities else 0.0
        swing = float(np.mean(swings)) if swings else 0.0
        hold = float(np.mean(holds)) if holds else 0.0

        state = "OBSERVATION"
        if consensus >= 0.72 and accumulation >= 0.55 and eff >= 2.0:
            state = "CONFIRMED"
        elif accumulation >= 0.45 and eff >= 1.5:
            state = "ACCUMULATION"
        elif positions and all(p.state == "EXIT" for p in positions):
            state = "EXIT"

        entry_prices=[p.average_entry_price for p in positions if p.current_balance_token>0 and p.average_entry_price]
        smart_avg_entry=float(np.mean(entry_prices)) if entry_prices else None
        current_price=float(store.token(e.token_mint).price_usd or 0.0)
        entry_distance=((current_price/smart_avg_entry)-1.0) if (smart_avg_entry and current_price>0) else None
        result = {
            "smart_money_consensus": consensus,
            "weighted_smart_capital_consensus": consensus,
            "qualified_wallet_count": float(raw),
            "effective_wallet_count": float(eff),
            "independence_factor": independence,
            "smart_capital_usd": total_capital,
            "accumulation_score": accumulation,
            "conviction_score": conviction,
            "average_wallet_quality": quality,
            "average_swing_score": swing,
            "average_hold_score": hold,
            "smart_capital_state": state,
            "smart_average_entry_price": smart_avg_entry,
            "entry_distance_price": entry_distance,
            "entry_validity": "ENTRY_TOO_LATE" if entry_distance is not None and entry_distance > float(self.cfg.get("max_entry_distance",0.60)) else "VALID",
            "smart_capital_confidence": min(1.0, 0.25 * raw + 0.35 * breadth + 0.40 * quality),
        }
        self.token_states[e.token_mint] = result
        return result
