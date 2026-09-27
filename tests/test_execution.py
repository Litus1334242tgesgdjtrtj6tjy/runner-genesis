from datetime import datetime,timezone
from runner_genesis.config import ExecutionConfig
from runner_genesis.execution import PaperExecutionEngine
from runner_genesis.ai_trader import TradeProposal,Action
from runner_genesis.domain.state import TokenState

def test_deterministic_execution():
    x=PaperExecutionEngine(ExecutionConfig(failed_tx_base_probability=0),seed=1)
    p=TradeProposal(Action.ENTER,'M',amount_eur=10)
    t=TokenState('M',price_usd=1,liquidity_usd=100000)
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    a=x.execute(p,t,now); b=x.execute(p,t,now)
    assert a.execution_price==b.execution_price
    assert a.latency_ms==b.latency_ms
