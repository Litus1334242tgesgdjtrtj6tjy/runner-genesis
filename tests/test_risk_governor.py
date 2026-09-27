from datetime import datetime, timezone, timedelta
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


def test_related_wallet_cohort_veto():
    g=RiskGovernor(RiskConfig(min_liquidity_usd=10000, max_correlated_exposure_pct=0.35))
    a=PaperAccount(300,300)
    t=TokenState('M',liquidity_usd=100000)
    p=TradeProposal(Action.ENTER,'M',amount_eur=10)
    d=g.evaluate(p,a,t,features={
        'sellability_score':1.0,
        'manipulation_risk':0.0,
        'entry_validity':'VALID',
        'cohort_concentration':0.9,
        'independence_ratio':0.4,
    })
    assert not d.approved
    assert 'WALLET_CLUSTER_CONCENTRATION' in d.reasons


def test_daily_spend_and_loss_reset_on_new_utc_day():
    cfg = RiskConfig(
        min_liquidity_usd=10000,
        max_daily_spend_eur=60,
        max_daily_loss_eur=30,
        max_account_pct_per_trade=1.0,
        max_position_eur=100,
    )
    g = RiskGovernor(cfg)
    a = PaperAccount(300, 300)
    token = TokenState('M', liquidity_usd=100000)
    p = TradeProposal(Action.ENTER, 'M', amount_eur=20)
    day1 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    day2 = day1 + timedelta(days=1)

    a.advance_accounting_day(day1)
    a.daily_spend_eur = 55
    a.daily_realized_pnl_eur = -40
    a.realized_pnl_eur = -100

    blocked = g.evaluate(
        p, a, token,
        features={'sellability_score':1.0,'manipulation_risk':0.0,'entry_validity':'VALID'},
        now=day1,
    )
    assert 'MAX_DAILY_SPEND' in blocked.reasons
    assert 'MAX_DAILY_LOSS' in blocked.reasons

    next_day = g.evaluate(
        p, a, token,
        features={'sellability_score':1.0,'manipulation_risk':0.0,'entry_validity':'VALID'},
        now=day2,
    )
    assert 'MAX_DAILY_SPEND' not in next_day.reasons
    assert 'MAX_DAILY_LOSS' not in next_day.reasons
    assert a.daily_spend_eur == 0
    assert a.daily_realized_pnl_eur == 0



def test_drawdown_does_not_block_risk_reduction():
    cfg = RiskConfig(
        min_liquidity_usd=10000,
        max_daily_loss_eur=10,
        max_portfolio_drawdown_pct=0.10,
        max_account_pct_per_trade=1.0,
        max_position_eur=100,
    )
    g = RiskGovernor(cfg)
    a = PaperAccount(300,300)
    now = datetime(2026,1,1,12,tzinfo=timezone.utc)
    a.advance_accounting_day(now)
    a.daily_realized_pnl_eur = -20
    a.equity_eur = 240
    a.peak_equity_eur = 300
    token = TokenState('M',liquidity_usd=100000)

    reduction = g.evaluate(
        TradeProposal(Action.REDUCE,'M',reduce_fraction=0.5),
        a, token,
        features={'sellability_score':1.0,'manipulation_risk':0.0,'entry_validity':'VALID'},
        now=now,
    )
    assert reduction.approved
    assert 'MAX_DAILY_LOSS' not in reduction.reasons
    assert 'MAX_DRAWDOWN' not in reduction.reasons
