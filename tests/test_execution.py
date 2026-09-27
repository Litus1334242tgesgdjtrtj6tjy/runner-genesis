from datetime import datetime,timezone
from runner_genesis.config import ExecutionConfig
from runner_genesis.execution import PaperExecutionEngine
from runner_genesis.ai_trader import TradeProposal,Action
from runner_genesis.domain.state import TokenState
from runner_genesis.execution import PaperFill
from runner_genesis.portfolio import PortfolioLedger

def test_deterministic_execution():
    x=PaperExecutionEngine(ExecutionConfig(failed_tx_base_probability=0),seed=1)
    p=TradeProposal(Action.ENTER,'M',amount_eur=10)
    t=TokenState('M',price_usd=1,liquidity_usd=100000)
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    a=x.execute(p,t,now); b=x.execute(p,t,now)
    assert a.execution_price==b.execution_price
    assert a.latency_ms==b.latency_ms



def test_network_fee_is_added_when_sol_price_is_known():
    cfg=ExecutionConfig(
        failed_tx_base_probability=0,
        base_fee_bps=0,
        priority_fee_bps=0,
        network_base_fee_lamports=5000,
        network_priority_fee_lamports=0,
        network_signature_count=1,
    )
    x=PaperExecutionEngine(cfg,seed=1)
    p=TradeProposal(Action.ENTER,'M',amount_eur=10)
    t=TokenState('M',price_usd=1,liquidity_usd=100000,metadata={'sol_usd':200.0})
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    fill=x.execute(p,t,now)
    assert fill is not None and not fill.failed
    assert abs(fill.network_fee_eur-0.001) < 1e-12
    assert abs(fill.fees_eur-0.001) < 1e-12


def test_failed_network_fee_reduces_paper_cash_and_daily_pnl():
    ledger=PortfolioLedger(300.0)
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    fill=PaperFill(
        token_mint='M', side='BUY', requested_eur=10.0, filled_eur=0.0,
        quantity=0.0, reference_price=1.0, execution_price=1.0,
        slippage_pct=0.0, fees_eur=0.001, latency_ms=100.0,
        failed=True, partial=False, timestamp=now, reason='SIMULATED_TX_FAILURE',
        network_fee_eur=0.001,
    )
    ledger.apply_fill(fill)
    a=ledger.account
    assert abs(a.cash_eur-299.999) < 1e-12
    assert abs(a.realized_pnl_eur+0.001) < 1e-12
    assert abs(a.daily_realized_pnl_eur+0.001) < 1e-12
