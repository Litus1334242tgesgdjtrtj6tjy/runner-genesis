from datetime import datetime, timezone

from runner_genesis.ai_trader import AIPaperTrader, Action
from runner_genesis.config import TraderConfig
from runner_genesis.execution import PaperFill
from runner_genesis.portfolio import PortfolioLedger


def _decision(trader, current_quantity, target_quantity):
    features = {
        "fusion_research_score": 0.6,
        "fusion_confidence": 0.6,
        "weighted_smart_capital_consensus": 0.4,
        "token_risk": 0.2,
        "manipulation_risk": 0.1,
        "entry_validity": "VALID",
        "signal_validity": "VALID",
        "data_quality_score": 0.8,
    }
    probs = {"genesis_prob": None, "genesis_score": 0.6}
    alpha = {"expected_executable_edge": 0.0, "sellability_score": 0.9}
    persistence = {"runner_persistence": 0.48, "distribution_score": 0.20}
    return trader.decide(
        "M",
        features,
        probs,
        alpha,
        persistence,
        True,
        current_cost=100.0,
        adds=0,
        current_quantity=current_quantity,
        moonbag_target_quantity=target_quantity,
    )


def _fill(side, qty, price, action=None, reduce_fraction=0.0):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return PaperFill(
        token_mint="M",
        side=side,
        requested_eur=qty * price,
        filled_eur=qty * price,
        quantity=qty,
        reference_price=price,
        execution_price=price,
        slippage_pct=0.0,
        fees_eur=0.0,
        latency_ms=0.0,
        failed=False,
        partial=False,
        timestamp=now,
        proposal_action=action,
        proposal_reduce_fraction=reduce_fraction,
    )


def test_runner_bag_reduces_to_absolute_target_only_once():
    trader = AIPaperTrader(TraderConfig(moonbag_fraction=0.15), paper_only=True)

    first = _decision(trader, 100.0, 0.0)
    assert first.action == Action.KEEP_RUNNER_BAG
    assert abs(first.reduce_fraction - 0.85) < 1e-12

    ledger = PortfolioLedger(300.0)
    assert ledger.apply_fill(_fill("BUY", 100.0, 1.0, action="ENTER"))
    position = ledger.account.positions["M"]

    # Simulate a liquidity-limited first runner-bag sale: only 10 of the requested 85
    # tokens execute. The durable target must still be 15 tokens, not 15% of the new 90.
    partial = _fill("SELL", 10.0, 1.0, action="KEEP_RUNNER_BAG", reduce_fraction=0.85)
    partial.partial = True
    assert ledger.apply_fill(partial)
    position = ledger.account.positions["M"]
    assert abs(position.quantity - 90.0) < 1e-12
    assert abs(position.moonbag_target_quantity - 15.0) < 1e-12

    second = _decision(trader, position.quantity, position.moonbag_target_quantity)
    assert second.action == Action.KEEP_RUNNER_BAG
    assert abs(second.reduce_fraction - (75.0 / 90.0)) < 1e-12

    assert ledger.apply_fill(_fill(
        "SELL", 75.0, 1.0,
        action="KEEP_RUNNER_BAG",
        reduce_fraction=second.reduce_fraction,
    ))
    position = ledger.account.positions["M"]
    assert abs(position.quantity - 15.0) < 1e-12

    third = _decision(trader, position.quantity, position.moonbag_target_quantity)
    assert third.action == Action.HOLD
    assert "RUNNER_BAG_TARGET_REACHED" in third.reasons


def test_add_resets_old_runner_bag_target():
    ledger = PortfolioLedger(300.0)
    assert ledger.apply_fill(_fill("BUY", 100.0, 1.0, action="ENTER"))
    position = ledger.account.positions["M"]
    position.moonbag_target_quantity = 15.0
    position.moonbag_locked_fraction = 1.0

    assert ledger.apply_fill(_fill("BUY", 10.0, 1.0, action="ADD"))
    position = ledger.account.positions["M"]
    assert position.moonbag_target_quantity == 0.0
    assert position.moonbag_locked_fraction == 0.0
