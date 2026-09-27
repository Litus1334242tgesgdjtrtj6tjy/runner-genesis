from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from math import exp
from statistics import median
from typing import Any

from ..domain.events import EventType, MarketEvent
from ..state_store import MarketStateStore
from .actor_graph import ActorGraphEngine
from .wallet_quality import WalletQualityEngine
from .discovery import PumpDiscoveryEngine


BUY_TYPES = {
    EventType.BUY,
    EventType.RUNNER_HOLDER_ENTRY,
    EventType.RUNNER_HOLDER_ADD,
    EventType.SMART_WALLET_NEW_ENTRY,
    EventType.SMART_WALLET_ADD,
}
SELL_TYPES = {
    EventType.SELL,
    EventType.RUNNER_HOLDER_REDUCE,
    EventType.RUNNER_HOLDER_EXIT,
    EventType.SMART_WALLET_REDUCE,
    EventType.SMART_WALLET_EXIT,
}


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


@dataclass
class WalletTokenPosition:
    wallet_address: str
    token_mint: str
    first_entry_time: datetime | None = None
    last_entry_time: datetime | None = None
    last_activity_time: datetime | None = None
    average_entry_price: float | None = None
    average_entry_market_cap: float | None = None
    bought_token: float = 0.0
    sold_token: float = 0.0
    bought_usd: float = 0.0
    sold_usd: float = 0.0
    invested_sol: float = 0.0
    buy_count: int = 0
    sell_count: int = 0
    estimated_liquid_capital_usd: float | None = None
    state: str = "NEW_POSITION"
    buy_sizes_usd: list[float] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)

    @property
    def current_exposure_usd(self) -> float:
        return max(0.0, self.bought_usd - self.sold_usd)

    @property
    def retained_fraction(self) -> float:
        if self.bought_token > 0:
            return _clip((self.bought_token - self.sold_token) / self.bought_token)
        if self.bought_usd > 0:
            return _clip((self.bought_usd - self.sold_usd) / self.bought_usd)
        return 0.0

    @property
    def adds(self) -> int:
        return max(0, self.buy_count - 1)

    @property
    def reductions(self) -> int:
        return self.sell_count


@dataclass
class SmartStateTransition:
    timestamp: datetime
    token_mint: str
    old_state: str
    new_state: str
    reason: str
    metrics_snapshot: dict[str, float | str | None]


class SmartCapitalEngine:
    """Point-in-time wallet-position and weighted-consensus engine.

    It deliberately separates discovery from qualification: a Pump/KOL source may explain
    where a wallet was found, but on-chain quality/strategy/conviction/independence decide
    whether that wallet contributes meaningful weight.
    """

    def __init__(self, cfg, wallet_quality: WalletQualityEngine, discovery: PumpDiscoveryEngine) -> None:
        self.cfg = cfg
        self.wallet_quality = wallet_quality
        self.discovery = discovery
        self.positions: dict[tuple[str, str], WalletTokenPosition] = {}
        self.wallet_trade_times: dict[str, list[datetime]] = defaultdict(list)
        self.wallet_closed_holds: dict[str, list[float]] = defaultdict(list)
        self.token_state: dict[str, str] = defaultdict(lambda: "OBSERVATION")
        self.transitions: list[SmartStateTransition] = []

    def _position(self, wallet: str, mint: str) -> WalletTokenPosition:
        key = (wallet, mint)
        if key not in self.positions:
            self.positions[key] = WalletTokenPosition(wallet_address=wallet, token_mint=mint)
        return self.positions[key]

    def observe(self, e: MarketEvent) -> None:
        if not self.cfg.enabled or not e.wallet or e.event_type not in BUY_TYPES | SELL_TYPES:
            return
        p = self._position(e.wallet, e.token_mint)
        p.last_activity_time = e.timestamp
        p.event_ids.append(e.event_id)
        self.wallet_trade_times[e.wallet].append(e.timestamp)
        usd = max(0.0, float(e.usd_value or 0.0))
        token = max(0.0, float(e.amount_token or 0.0))
        sol = max(0.0, float(e.sol_value or 0.0))

        cap = e.metadata.get("estimated_liquid_capital_usd") if e.metadata else None
        if cap is not None:
            try:
                p.estimated_liquid_capital_usd = max(0.0, float(cap))
            except (TypeError, ValueError):
                pass

        if e.event_type in BUY_TYPES:
            if p.first_entry_time is None:
                p.first_entry_time = e.timestamp
            p.last_entry_time = e.timestamp
            old_bought_usd = p.bought_usd
            p.buy_count += 1
            p.bought_usd += usd
            p.bought_token += token
            p.invested_sol += sol
            if usd > 0:
                p.buy_sizes_usd.append(usd)
            if e.price_usd is not None and e.price_usd > 0:
                if old_bought_usd > 0 and p.average_entry_price is not None and usd > 0:
                    p.average_entry_price = (p.average_entry_price * old_bought_usd + float(e.price_usd) * usd) / (old_bought_usd + usd)
                elif p.average_entry_price is None:
                    p.average_entry_price = float(e.price_usd)
            if e.market_cap_usd is not None and e.market_cap_usd > 0:
                if old_bought_usd > 0 and p.average_entry_market_cap is not None and usd > 0:
                    p.average_entry_market_cap = (p.average_entry_market_cap * old_bought_usd + float(e.market_cap_usd) * usd) / (old_bought_usd + usd)
                elif p.average_entry_market_cap is None:
                    p.average_entry_market_cap = float(e.market_cap_usd)
            p.state = "NEW_POSITION" if p.buy_count == 1 else "ADD"

        elif e.event_type in SELL_TYPES:
            p.sell_count += 1
            p.sold_usd += usd
            p.sold_token += token
            old_state = p.state
            if p.retained_fraction <= 0.02:
                p.state = "EXIT"
                if p.first_entry_time is not None:
                    self.wallet_closed_holds[e.wallet].append(max(0.0, (e.timestamp - p.first_entry_time).total_seconds()))
            else:
                p.state = "REDUCE"

    def position_snapshot(self, wallet: str, mint: str, now: datetime) -> dict[str, Any]:
        p = self.positions.get((wallet, mint))
        if not p:
            return {}
        hold = max(0.0, (now - p.first_entry_time).total_seconds()) if p.first_entry_time else 0.0
        return {
            **asdict(p),
            "current_exposure_usd": p.current_exposure_usd,
            "retained_fraction": p.retained_fraction,
            "hold_time_seconds": hold,
            "adds": p.adds,
            "reductions": p.reductions,
        }

    def wallet_style(self, wallet: str, now: datetime) -> str:
        holds = list(self.wallet_closed_holds.get(wallet, []))
        active_holds = [
            max(0.0, (now - p.first_entry_time).total_seconds())
            for (w, _), p in self.positions.items()
            if w == wallet and p.first_entry_time and p.retained_fraction > 0.02
        ]
        sample = holds + active_holds
        if not sample:
            return "UNKNOWN"
        med = median(sample)
        trade_count = len(self.wallet_trade_times.get(wallet, []))
        if med < 300 and trade_count >= 4:
            return "SCALPER"
        if med >= 6 * 3600:
            return "HOLDER"
        if med >= 45 * 60:
            return "SWING"
        if med >= 10 * 60:
            return "RUNNER"
        return "MIXED"

    @staticmethod
    def strategy_match(style: str) -> float:
        return {
            "HOLDER": 1.0,
            "SWING": 0.95,
            "RUNNER": 0.90,
            "MIXED": 0.65,
            "UNKNOWN": 0.50,
            "SCALPER": 0.35,
        }.get(style, 0.50)

    def conviction(self, p: WalletTokenPosition, store: MarketStateStore) -> tuple[float, float]:
        w = store.wallets.get(p.wallet_address)
        history = [float(x[1]) for x in (w.buys if w else []) if float(x[1] or 0) > 0]
        last_size = p.buy_sizes_usd[-1] if p.buy_sizes_usd else 0.0
        vs_median = None
        score_parts = []
        confidence_parts = []
        if history and last_size > 0:
            med = median(history)
            if med > 0:
                vs_median = last_size / med
                score_parts.append(_clip(vs_median / 2.0))
                confidence_parts.append(min(1.0, len(history) / 10.0))
        if p.estimated_liquid_capital_usd and p.estimated_liquid_capital_usd > 0 and p.current_exposure_usd > 0:
            relative = p.current_exposure_usd / p.estimated_liquid_capital_usd
            score_parts.append(_clip(relative / 0.10))
            confidence_parts.append(1.0)
        if not score_parts:
            return 0.0, 0.0
        return sum(score_parts) / len(score_parts), sum(confidence_parts) / len(confidence_parts)

    def accumulation(self, p: WalletTokenPosition, now: datetime) -> float:
        if p.buy_count <= 0:
            return 0.0
        add_score = _clip(p.adds / 3.0)
        retention = p.retained_fraction
        hold = max(0.0, (now - p.first_entry_time).total_seconds()) if p.first_entry_time else 0.0
        hold_score = _clip(hold / 3600.0)
        progression = 0.5
        if len(p.buy_sizes_usd) >= 2 and p.buy_sizes_usd[0] > 0:
            progression = _clip((p.buy_sizes_usd[-1] / p.buy_sizes_usd[0]) / 1.5)
        return _clip(0.30 * add_score + 0.35 * retention + 0.20 * hold_score + 0.15 * progression)

    def wallet_metrics(self, wallet: str, as_of: datetime, store: MarketStateStore) -> dict[str, Any]:
        q = self.wallet_quality.compute(wallet, as_of, store)
        hist = store.resolved_wallet_history_as_of(wallet, as_of)
        returns = [float(x.realized_return) for x in hist if x.realized_return is not None]
        wins = [x for x in returns if x > 0]
        losses = [x for x in returns if x < 0]
        total_gain = sum(wins)
        total_loss = abs(sum(losses))
        profit_factor = (total_gain / total_loss) if total_loss > 0 else None
        sorted_pnl = sorted((max(0.0, x) for x in returns), reverse=True)
        total_positive = sum(sorted_pnl)
        def share(k: int) -> float | None:
            if total_positive <= 0:
                return None
            return sum(sorted_pnl[:k]) / total_positive
        consistency = None
        if returns:
            mean = sum(returns) / len(returns)
            variance = sum((x - mean) ** 2 for x in returns) / len(returns)
            consistency = _clip(0.5 + 0.25 * mean - 0.25 * (variance ** 0.5))
        discovery = self.discovery.wallet_context(wallet, as_of)
        return {
            "wallet_address": wallet,
            "sample_size": len(hist),
            "win_rate": (sum(x > 0 for x in returns) / len(returns)) if returns else None,
            "profit_factor": profit_factor,
            "median_roi": median(returns) if returns else None,
            "average_roi": (sum(returns) / len(returns)) if returns else None,
            "largest_win": max(returns) if returns else None,
            "largest_loss": min(returns) if returns else None,
            "loss_rate": (sum(x < 0 for x in returns) / len(returns)) if returns else None,
            "top1_pnl_share": share(1),
            "top3_pnl_share": share(3),
            "top5_pnl_share": share(5),
            "consistency_score": consistency,
            "repeatability_score": q.runner_hit_rate if hist else None,
            "diversification_score": None,
            "wallet_quality_score": q.quality,
            "runner_score": q.runner_hit_rate,
            "hold_score": _clip(q.median_winner_hold_seconds / (6 * 3600)) if q.sample_size else 0.0,
            "swing_score": _clip(q.median_winner_hold_seconds / (2 * 3600)) if q.sample_size else 0.0,
            "wallet_style": self.wallet_style(wallet, as_of),
            "confidence": min(1.0, q.sample_size / max(float(self.cfg.quality_sample_target), 1.0)),
            **discovery,
        }

    @staticmethod
    def _window_stats(observations) -> dict[str, Any]:
        returns = [float(x.realized_return) for x in observations if x.realized_return is not None]
        if not returns:
            return {
                "sample_size": len(observations),
                "win_rate": None,
                "profit_factor": None,
                "average_roi": None,
                "median_roi": None,
                "largest_win": None,
                "largest_loss": None,
                "max_drawdown": None,
                "top1_pnl_share": None,
                "top3_pnl_share": None,
                "top5_pnl_share": None,
                "consistency_score": None,
                "repeatability_score": None,
                "diversification_score": None,
                "tokens_2x": 0,
                "tokens_3x": 0,
                "tokens_5x": 0,
                "tokens_10x": 0,
                "tokens_20x": 0,
                "net_pnl": None,
            }
        wins = [x for x in returns if x > 0]
        losses = [x for x in returns if x < 0]
        gains = sum(wins)
        loss_abs = abs(sum(losses))
        profit_factor = gains / loss_abs if loss_abs > 0 else None
        positives = sorted((max(0.0, x) for x in returns), reverse=True)
        total_positive = sum(positives)

        def share(k: int):
            return sum(positives[:k]) / total_positive if total_positive > 0 else None

        mean = sum(returns) / len(returns)
        variance = sum((x - mean) ** 2 for x in returns) / len(returns)
        sigma = variance ** 0.5
        consistency = _clip(0.50 + 0.20 * mean - 0.18 * sigma)
        top1 = share(1)
        diversification = _clip(1.0 - float(top1 or 0.0))
        repeatability = _clip(0.55 * (sum(x >= 1.0 for x in returns) / len(returns)) + 0.45 * (len(wins) / len(returns)))

        # Equal-risk-unit drawdown proxy. This is not labelled as cash drawdown because
        # historical position sizes can be unknown.
        equity = peak = 1.0
        max_dd = 0.0
        for r in returns:
            equity *= max(0.0, 1.0 + max(-1.0, r))
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / max(peak, 1e-12))

        pnl_known = [
            float(o.buy_eur) * float(o.realized_return)
            for o in observations
            if o.realized_return is not None and float(o.buy_eur or 0.0) > 0
        ]
        # net_pnl is only emitted when every resolved observation carries a common
        # fiat-like quote notional. Mixed/unknown SOL quote values remain None.
        net_pnl = sum(pnl_known) if len(pnl_known) == len(returns) else None
        return {
            "sample_size": len(observations),
            "win_rate": len(wins) / len(returns),
            "profit_factor": profit_factor,
            "average_roi": mean,
            "median_roi": median(returns),
            "largest_win": max(returns),
            "largest_loss": min(returns),
            "max_drawdown": max_dd,
            "top1_pnl_share": top1,
            "top3_pnl_share": share(3),
            "top5_pnl_share": share(5),
            "consistency_score": consistency,
            "repeatability_score": repeatability,
            "diversification_score": diversification,
            "tokens_2x": sum(x >= 1.0 for x in returns),
            "tokens_3x": sum(x >= 2.0 for x in returns),
            "tokens_5x": sum(x >= 4.0 for x in returns),
            "tokens_10x": sum(x >= 9.0 for x in returns),
            "tokens_20x": sum(x >= 19.0 for x in returns),
            "net_pnl": net_pnl,
        }

    def wallet_metrics_window(self, wallet: str, as_of: datetime, store: MarketStateStore, days: int = 30) -> dict[str, Any]:
        cutoff = as_of - timedelta(days=max(1, int(days)))
        observations = [
            o for o in store.resolved_wallet_history_as_of(wallet, as_of)
            if o.resolved_at >= cutoff
        ]
        stats = self._window_stats(observations)
        full = self.wallet_metrics(wallet, as_of, store)
        quality = float(full.get("wallet_quality_score") or 0.0)
        swing = float(full.get("swing_score") or 0.0)
        hold = float(full.get("hold_score") or 0.0)
        consistency = float(stats.get("consistency_score") or 0.0)
        repeatability = float(stats.get("repeatability_score") or 0.0)
        diversification = float(stats.get("diversification_score") or 0.0)
        dd = float(stats.get("max_drawdown") or 0.0)
        sample_quality = _clip(float(stats["sample_size"]) / 20.0)
        smart_30d_score = _clip(
            0.25 * quality
            + 0.18 * consistency
            + 0.17 * repeatability
            + 0.12 * diversification
            + 0.10 * (1.0 - dd)
            + 0.08 * swing
            + 0.05 * hold
            + 0.05 * sample_quality
        )
        return {
            **full,
            **stats,
            "window_days": int(days),
            "smart_capital_30d_score": smart_30d_score,
            "data_quality_score": _clip(0.55 * sample_quality + 0.45 * float(full.get("confidence") or 0.0)),
        }

    def emerging_wallet_metrics(self, wallet: str, as_of: datetime, store: MarketStateStore) -> dict[str, Any]:
        m7 = self.wallet_metrics_window(wallet, as_of, store, 7)
        m30 = self.wallet_metrics_window(wallet, as_of, store, 30)
        q7 = float(m7.get("smart_capital_30d_score") or 0.0)
        q30 = float(m30.get("smart_capital_30d_score") or 0.0)
        growth = max(-1.0, min(1.0, q7 - q30))
        recent_sample = int(m7.get("sample_size") or 0)
        concentration = float(m7.get("top1_pnl_share") or 1.0)
        consistency = float(m7.get("consistency_score") or 0.0)
        repeatability = float(m7.get("repeatability_score") or 0.0)
        score = _clip(
            0.30 * _clip(0.5 + growth)
            + 0.22 * consistency
            + 0.20 * repeatability
            + 0.13 * _clip(recent_sample / 8.0)
            + 0.15 * _clip(1.0 - concentration)
        )
        qualifies = bool(recent_sample >= 5 and score >= 0.60 and concentration <= 0.70)
        return {
            "wallet_address": wallet,
            "emerging_smart_wallet_score": score,
            "emerging_smart_wallet": qualifies,
            "quality_velocity_7d_vs_30d": growth,
            "recent_sample_size_7d": recent_sample,
            "recent_top1_pnl_share": m7.get("top1_pnl_share"),
            "recent_consistency": m7.get("consistency_score"),
            "recent_repeatability": m7.get("repeatability_score"),
        }

    def true_smart_capital_30d(self, wallets: list[str], as_of: datetime, store: MarketStateStore, limit: int = 100) -> list[dict[str, Any]]:
        rows = []
        for wallet in dict.fromkeys(w for w in wallets if w):
            row = self.wallet_metrics_window(wallet, as_of, store, 30)
            row.update(self.emerging_wallet_metrics(wallet, as_of, store))
            rows.append(row)
        rows.sort(
            key=lambda x: (
                float(x.get("smart_capital_30d_score") or 0.0),
                int(x.get("sample_size") or 0),
            ),
            reverse=True,
        )
        return rows[: max(1, int(limit))]

    def token_features(self, mint: str, now: datetime, store: MarketStateStore, actor: ActorGraphEngine) -> dict[str, float | str | None]:
        active = [p for (w, m), p in self.positions.items() if m == mint and p.retained_fraction > 0.02]
        wallets = [p.wallet_address for p in active]
        cohort = actor.cohort_features(wallets)
        eff = float(cohort["effective_wallet_count"])

        contributions = []
        capitals = []
        qualities = []
        strategies = []
        swings = []
        holds = []
        accumulations = []
        convictions = []
        price_num = price_den = 0.0
        mc_num = mc_den = 0.0

        for p in active:
            q = self.wallet_quality.compute(p.wallet_address, now, store)
            style = self.wallet_style(p.wallet_address, now)
            strategy = self.strategy_match(style)
            conviction, conviction_conf = self.conviction(p, store)
            accum = self.accumulation(p, now)
            age = max(0.0, (now - (p.last_activity_time or now)).total_seconds())
            event_freshness = exp(-age / max(float(self.cfg.freshness_half_life_seconds), 1.0))
            # Continuing to hold most of a position is itself fresh state evidence for a
            # swing/persistence strategy; do not decay an intact holder to zero merely
            # because it has not generated a new transaction in the last few minutes.
            freshness = max(event_freshness, 0.65 * p.retained_fraction)
            independence = actor.independence_factor(p.wallet_address, wallets)
            contribution = q.quality * strategy * max(conviction, 0.15) * freshness * independence
            contributions.append(contribution)
            capital = max(p.current_exposure_usd, 1.0)
            capitals.append(capital)
            qualities.append(q.quality)
            strategies.append(strategy)
            swings.append(1.0 if style == "SWING" else 0.75 if style in {"HOLDER", "RUNNER"} else 0.25)
            holds.append(_clip(q.median_winner_hold_seconds / (6 * 3600)) if q.sample_size else (0.8 if style == "HOLDER" else 0.5 if style == "SWING" else 0.2))
            accumulations.append(accum)
            convictions.append(conviction)
            if p.average_entry_price is not None:
                price_num += p.average_entry_price * capital
                price_den += capital
            if p.average_entry_market_cap is not None:
                mc_num += p.average_entry_market_cap * capital
                mc_den += capital

        raw = len(active)
        mean_contribution = sum(contributions) / max(raw, 1)
        breadth = _clip(eff / 3.0)
        consensus = _clip(0.72 * mean_contribution + 0.28 * breadth)
        accumulation = sum(accumulations) / max(len(accumulations), 1)
        conviction = sum(convictions) / max(len(convictions), 1)
        avg_quality = sum(qualities) / max(len(qualities), 1)
        avg_strategy = sum(strategies) / max(len(strategies), 1)
        avg_swing = sum(swings) / max(len(swings), 1)
        avg_hold = sum(holds) / max(len(holds), 1)
        smart_entry_price = price_num / price_den if price_den else None
        smart_entry_mc = mc_num / mc_den if mc_den else None
        token = store.token(mint)
        entry_distance_price = (token.price_usd / smart_entry_price - 1.0) if token.price_usd and smart_entry_price else None
        entry_distance_mc = (token.market_cap_usd / smart_entry_mc - 1.0) if token.market_cap_usd and smart_entry_mc else None

        retained = [p.retained_fraction for p in active]
        weighted_retention = sum(r * c for r, c in zip(retained, capitals)) / max(sum(capitals), 1e-9) if active else 0.0
        distribution = _clip(1.0 - weighted_retention) if active else 0.0

        known = [
            1.0 if token.price_usd is not None else 0.0,
            1.0 if token.market_cap_usd is not None else 0.0,
            1.0 if token.liquidity_usd is not None else 0.0,
            1.0 if raw > 0 else 0.0,
            min(1.0, avg_quality / 0.5) if raw else 0.0,
        ]
        data_quality = sum(known) / len(known)

        signal_valid = (
            consensus >= float(self.cfg.min_consensus)
            and eff >= float(self.cfg.min_effective_wallets)
            and accumulation >= float(self.cfg.min_accumulation)
            and conviction >= float(self.cfg.min_conviction)
            and avg_quality >= float(self.cfg.min_wallet_quality)
            and avg_strategy >= float(self.cfg.min_strategy_match)
        )
        if entry_distance_price is None:
            entry_validity = "WAITING_DATA"
        elif entry_distance_price > float(self.cfg.max_entry_distance_price):
            entry_validity = "ENTRY_TOO_LATE"
        elif signal_valid:
            entry_validity = "VALID"
        else:
            entry_validity = "NOT_CONFIRMED"

        current = self.token_state[mint]
        if raw == 0:
            new_state = "OBSERVATION"
            reason = "NO_ACTIVE_SMART_POSITIONS"
        elif distribution >= float(self.cfg.distribution_exit_threshold):
            new_state = "DISTRIBUTION"
            reason = "DISTRIBUTION_HIGH"
        elif signal_valid:
            new_state = "CONFIRMED"
            reason = "WEIGHTED_CONSENSUS_CONFIRMED"
        elif accumulation >= float(self.cfg.min_accumulation):
            new_state = "ACCUMULATION"
            reason = "ACCUMULATION_FORMING"
        else:
            new_state = "OBSERVATION"
            reason = "INSUFFICIENT_CONSENSUS"
        self._transition(mint, now, current, new_state, reason, {
            "consensus": consensus,
            "accumulation": accumulation,
            "distribution": distribution,
            "effective_wallet_count": eff,
        })

        return {
            "qualified_wallet_count": float(raw),
            **cohort,
            "total_smart_capital_usd": float(sum(p.current_exposure_usd for p in active)),
            "weighted_smart_capital_consensus": consensus,
            "smart_money_consensus": consensus,
            "accumulation_score": accumulation,
            "conviction_score": conviction,
            "average_wallet_quality": avg_quality,
            "average_strategy_match": avg_strategy,
            "average_swing_score": avg_swing,
            "average_hold_score": avg_hold,
            "smart_average_entry_price": smart_entry_price,
            "smart_average_entry_market_cap": smart_entry_mc,
            "entry_distance_price": entry_distance_price,
            "entry_distance_market_cap": entry_distance_mc,
            "smart_capital_retention": weighted_retention,
            "smart_distribution_score": distribution,
            "smart_capital_state": self.token_state[mint],
            "signal_validity": "VALID" if signal_valid else "NOT_CONFIRMED",
            "entry_validity": entry_validity,
            "data_quality_score": data_quality,
        }

    def apply_persistence(self, mint: str, now: datetime, persistence: float, distribution: float, feature_snapshot: dict[str, Any]) -> str:
        current = self.token_state[mint]
        if distribution >= float(self.cfg.distribution_exit_threshold):
            new = "EXIT"
            reason = "STRONG_DISTRIBUTION"
        elif distribution >= float(self.cfg.distribution_protect_threshold):
            new = "PROTECT"
            reason = "DISTRIBUTION_RISING"
        elif persistence >= float(self.cfg.state_persistence_threshold) and current in {"CONFIRMED", "ACCUMULATION", "PERSISTENCE"}:
            new = "PERSISTENCE"
            reason = "PERSISTENCE_CONFIRMED"
        else:
            new = current
            reason = "STATE_MAINTAINED"
        self._transition(mint, now, current, new, reason, {
            "persistence": persistence,
            "distribution": distribution,
            "consensus": feature_snapshot.get("weighted_smart_capital_consensus"),
        })
        return self.token_state[mint]

    def _transition(self, mint: str, now: datetime, old: str, new: str, reason: str, metrics: dict[str, Any]) -> None:
        if old == new:
            return
        self.token_state[mint] = new
        self.transitions.append(SmartStateTransition(now, mint, old, new, reason, dict(metrics)))

    def active_token_rows(self, now: datetime, store: MarketStateStore, actor: ActorGraphEngine) -> list[dict[str, Any]]:
        mints = sorted({m for _, m in self.positions})
        rows = []
        for mint in mints:
            f = self.token_features(mint, now, store, actor)
            rows.append({"token": mint, **f})
        return rows
