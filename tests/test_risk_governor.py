from runner_genesis.config import RiskConfig
from runner_genesis.risk_governor import RiskGovernor
from runner_genesis.ai_trader import TradeProposal,Action
from runner_genesis.domain.state import PaperAccount,TokenState

def test_low_liquidity_veto():
    g=RiskGovernor(RiskConfig(min_liquidity_usd=10000))
    a=PaperAccount(300,300)
    t=TokenState('M',liquidity_usd=100)
    p=TradeProposal(Action.ENTER,'M',amount_eur=10)
    d=g.evaluate(p,a,t)
    assert not d.approved
    assert 'MIN_LIQUIDITY' in d.reasons
