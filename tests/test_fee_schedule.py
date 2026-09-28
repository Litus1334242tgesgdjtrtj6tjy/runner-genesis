from datetime import datetime, timezone

from runner_genesis.ai_trader import Action, TradeProposal
from runner_genesis.config import ExecutionConfig
from runner_genesis.domain.state import TokenState
from runner_genesis.execution import PaperExecutionEngine
from runner_genesis.fees import PumpFeeSchedule


def test_pump_bonding_curve_uses_current_total_fee():
    token = TokenState(
        token_mint="M",
        market_cap_usd=50_000,
        metadata={"launchpad": "PUMP_FUN", "protocol": "pump.fun", "quote_asset": "SOL"},
    )
    q = PumpFeeSchedule().quote(token)
    assert q.protocol_fee_bps == 125.0
    assert q.source == "PUMP_BONDING_CURVE"


def test_pumpswap_usdc_canonical_fee_tier():
    token = TokenState(
        token_mint="M",
        migration_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        market_cap_usd=550_000,
        metadata={
            "launchpad": "PUMP_FUN",
            "protocol": "PUMPSWAP",
            "quote_asset": "USDC",
            "pump_pool_canonical": True,
        },
    )
    q = PumpFeeSchedule().quote(token)
    assert q.protocol_fee_bps == 110.0
    assert q.source == "PUMPSWAP_CANONICAL_USDC"


def test_non_pump_asset_falls_back_to_configured_execution_fee():
    token = TokenState(
        token_mint="M",
        price_usd=1.0,
        liquidity_usd=100_000.0,
        metadata={"protocol": "OTHER_DEX"},
    )
    cfg = ExecutionConfig(
        base_fee_bps=35,
        priority_fee_bps=10,
        failed_tx_base_probability=0.0,
    )
    fill = PaperExecutionEngine(cfg).execute(
        TradeProposal(Action.ENTER, "M", amount_eur=10.0),
        token,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert fill is not None and not fill.failed
    assert fill.protocol_fee_bps == 35.0
    assert abs(fill.fees_eur - 0.045) < 1e-9


def test_pump_paper_fill_charges_protocol_tier_plus_configured_overhead():
    token = TokenState(
        token_mint="M",
        price_usd=1.0,
        liquidity_usd=100_000.0,
        metadata={"launchpad": "PUMP_FUN", "protocol": "pump.fun"},
    )
    cfg = ExecutionConfig(
        base_fee_bps=35,
        priority_fee_bps=10,
        failed_tx_base_probability=0.0,
    )
    fill = PaperExecutionEngine(cfg).execute(
        TradeProposal(Action.ENTER, "M", amount_eur=10.0),
        token,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert fill is not None and not fill.failed
    assert fill.protocol_fee_bps == 125.0
    assert fill.fee_schedule_version == "PUMP_FEES_2026-05-21"
    assert abs(fill.fees_eur - 0.135) < 1e-9
