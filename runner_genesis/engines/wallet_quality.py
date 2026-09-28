from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
from ..state_store import MarketStateStore


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


@dataclass
class WalletQuality:
    sample_size: int = 0
    runner_hit_rate: float = 0.0
    median_runner_capture: float = 0.0
    median_winner_hold_seconds: float = 0.0
    median_entry_mc: float = 0.0
    quality: float = 0.0
    role: str = "UNKNOWN"
    win_rate: float | None = None
    profit_factor: float | None = None
    consistency_score: float | None = None
    repeatability_score: float | None = None
    top1_pnl_share: float | None = None
    top3_pnl_share: float | None = None
    top5_pnl_share: float | None = None
    p25_hold_seconds: float | None = None
    p75_hold_seconds: float | None = None
    p90_hold_seconds: float | None = None
    confidence: float = 0.0

    def as_features(self) -> dict[str, float | str | None]:
        return asdict(self)


class WalletQualityEngine:
    """Point-in-time wallet quality using only outcomes resolved by ``as_of``.

    The score deliberately shrinks small samples instead of allowing one lucky trade to
    create a high-quality wallet. Unknown metrics remain ``None``.
    """

    def compute(self, wallet: str | None, as_of: datetime, store: MarketStateStore) -> WalletQuality:
        if not wallet:
            return WalletQuality()
        obs = store.resolved_wallet_history_as_of(wallet, as_of)
        if not obs:
            return WalletQuality()

        returns = np.array([o.realized_return for o in obs if o.realized_return is not None], dtype=float)
        captures = np.array([o.runner_capture_ratio for o in obs if o.runner_capture_ratio is not None], dtype=float)
        winner_holds = np.array([o.hold_seconds for o in obs if o.hold_seconds is not None and (o.realized_return or 0) > 0], dtype=float)
        all_holds = np.array([o.hold_seconds for o in obs if o.hold_seconds is not None], dtype=float)
        mcs = np.array([o.entry_mc for o in obs if o.entry_mc is not None], dtype=float)

        runner_hit = float(np.mean(returns >= 1.0)) if len(returns) else 0.0
        win_rate = float(np.mean(returns > 0)) if len(returns) else None
        cap = float(np.median(captures)) if len(captures) else 0.0
        hold = float(np.median(winner_holds)) if len(winner_holds) else 0.0
        entry_mc = float(np.median(mcs)) if len(mcs) else 0.0

        gains = returns[returns > 0] if len(returns) else np.array([], dtype=float)
        losses = returns[returns < 0] if len(returns) else np.array([], dtype=float)
        profit_factor = None
        if len(returns):
            loss_sum = abs(float(losses.sum()))
            profit_factor = float(gains.sum()) / loss_sum if loss_sum > 0 else None

        top_shares = (None, None, None)
        positives = sorted((float(x) for x in gains), reverse=True)
        total_positive = sum(positives)
        if total_positive > 0:
            top_shares = tuple(sum(positives[:k]) / total_positive for k in (1, 3, 5))

        consistency = None
        if len(returns):
            mu = float(np.mean(returns))
            sigma = float(np.std(returns))
            consistency = _clip(0.50 + 0.20 * mu - 0.18 * sigma)

        concentration_penalty = float(top_shares[0] or 0.0)
        drawdown_proxy = _clip(abs(float(losses.min())) if len(losses) else 0.0)
        pf_score = _clip(float(profit_factor) / 2.0) if profit_factor is not None else 0.5 if len(returns) else 0.0
        consistency_value = float(consistency or 0.0)
        repeatability = _clip(0.55 * runner_hit + 0.45 * float(win_rate or 0.0))
        diversification = _clip(1.0 - concentration_penalty)
        sample_score = _clip(len(obs) / 30.0)
        realized_quality = _clip(0.5 + (float(np.median(returns)) if len(returns) else 0.0) / 2.0)
        quality_raw = (
            0.25 * consistency_value
            + 0.20 * realized_quality
            + 0.15 * pf_score
            + 0.15 * repeatability
            + 0.10 * (1.0 - drawdown_proxy)
            + 0.10 * diversification
            + 0.05 * sample_score
        )
        # Bayesian-style shrinkage toward zero for small samples.
        quality = quality_raw * sample_score

        if cap >= 0.45 and hold >= 1200 and runner_hit >= 0.20:
            role = "ELITE_RUNNER_HOLDER"
        elif cap >= 0.25 and hold >= 600:
            role = "RUNNER_HOLDER"
        elif hold < 240 and (win_rate or 0.0) >= 0.35:
            role = "SCALPER"
        elif entry_mc and entry_mc < 100_000 and runner_hit >= 0.20:
            role = "LEADER"
        else:
            role = "FOLLOWER"

        p25 = float(np.quantile(all_holds, 0.25)) if len(all_holds) else None
        p75 = float(np.quantile(all_holds, 0.75)) if len(all_holds) else None
        p90 = float(np.quantile(all_holds, 0.90)) if len(all_holds) else None
        return WalletQuality(
            sample_size=len(obs),
            runner_hit_rate=runner_hit,
            median_runner_capture=cap,
            median_winner_hold_seconds=hold,
            median_entry_mc=entry_mc,
            quality=quality,
            role=role,
            win_rate=win_rate,
            profit_factor=profit_factor,
            consistency_score=consistency,
            repeatability_score=repeatability,
            top1_pnl_share=top_shares[0],
            top3_pnl_share=top_shares[1],
            top5_pnl_share=top_shares[2],
            p25_hold_seconds=p25,
            p75_hold_seconds=p75,
            p90_hold_seconds=p90,
            confidence=sample_score,
        )
