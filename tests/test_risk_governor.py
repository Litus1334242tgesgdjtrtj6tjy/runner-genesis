from datetime import datetime, timezone, timedelta
from runner_genesis.config import RiskConfig
from runner_genesis.risk_governor import RiskGovernor
from runner_genesis.ai_trader import TradeProposal,Action
from runner_genesis.domain.state import PaperAccount,TokenState,PaperPosition

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



def test_cross_position_wallet_cluster_exposure_veto():
    cfg = RiskConfig(
        min_liquidity_usd=10000,
        max_correlated_exposure_pct=0.35,
        min_cluster_fraction_for_exposure=0.50,
        max_account_pct_per_trade=1.0,
        max_position_eur=200.0,
        max_simultaneous_positions=10,
    )
    g = RiskGovernor(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = PaperAccount(300, 300)
    a.positions["OLD"] = PaperPosition(
        token_mint="OLD",
        quantity=80.0,
        avg_entry_price=1.0,
        cost_basis_eur=80.0,
        opened_at=now,
        last_updated_at=now,
        risk_cluster_id="actor-cluster:abc",
        risk_cluster_fraction=0.8,
    )
    token = TokenState("NEW", liquidity_usd=100000)
    proposal = TradeProposal(Action.ENTER, "NEW", amount_eur=30.0)
    blocked = g.evaluate(
        proposal, a, token,
        features={
            "sellability_score": 1.0,
            "manipulation_risk": 0.0,
            "entry_validity": "VALID",
            "dominant_actor_cluster_id": "actor-cluster:abc",
            "dominant_actor_cluster_fraction": 0.8,
        },
        now=now,
    )
    assert not blocked.approved
    assert "MAX_WALLET_CLUSTER_EXPOSURE" in blocked.reasons

    other = g.evaluate(
        proposal, a, token,
        features={
            "sellability_score": 1.0,
            "manipulation_risk": 0.0,
            "entry_validity": "VALID",
            "dominant_actor_cluster_id": "actor-cluster:different",
            "dominant_actor_cluster_fraction": 0.8,
        },
        now=now,
    )
    assert "MAX_WALLET_CLUSTER_EXPOSURE" not in other.reasons


def test_minor_cluster_fraction_does_not_trigger_portfolio_cluster_cap():
    cfg = RiskConfig(
        min_liquidity_usd=10000,
        max_correlated_exposure_pct=0.35,
        min_cluster_fraction_for_exposure=0.50,
        max_account_pct_per_trade=1.0,
        max_position_eur=200.0,
        max_simultaneous_positions=10,
    )
    g = RiskGovernor(cfg)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = PaperAccount(300, 300)
    a.positions["OLD"] = PaperPosition(
        "OLD", 100.0, 1.0, 100.0, now, now,
        risk_cluster_id="actor-cluster:abc",
        risk_cluster_fraction=0.8,
    )
    token = TokenState("NEW", liquidity_usd=100000)
    decision = g.evaluate(
        TradeProposal(Action.ENTER, "NEW", amount_eur=20.0),
        a, token,
        features={
            "sellability_score": 1.0,
            "manipulation_risk": 0.0,
            "entry_validity": "VALID",
            "dominant_actor_cluster_id": "actor-cluster:abc",
            "dominant_actor_cluster_fraction": 0.30,
        },
        now=now,
    )
    assert "MAX_WALLET_CLUSTER_EXPOSURE" not in decision.reasons



def test_entry_fees_count_toward_position_and_cash_limits():
    cfg = RiskConfig(
        min_liquidity_usd=10000,
        max_account_pct_per_trade=1.0,
        max_position_eur=10.0,
        max_daily_spend_eur=100.0,
    )
    g = RiskGovernor(cfg)
    a = PaperAccount(10.0, 10.0)
    token = TokenState("M", liquidity_usd=100000)
    proposal = TradeProposal(Action.ENTER, "M", amount_eur=10.0)
    d = g.evaluate(
        proposal,
        a,
        token,
        features={
            "sellability_score": 1.0,
            "manipulation_risk": 0.0,
            "entry_validity": "VALID",
            "estimated_entry_fee_eur": 0.20,
        },
    )
    assert not d.approved
    assert "MAX_POSITION" in d.reasons
    assert "INSUFFICIENT_CASH" in d.reasons


def test_entry_fees_count_toward_daily_spend_limit():
    cfg = RiskConfig(
        min_liquidity_usd=10000,
        max_account_pct_per_trade=1.0,
        max_position_eur=100.0,
        max_daily_spend_eur=20.0,
    )
    g = RiskGovernor(cfg)
    a = PaperAccount(300.0, 300.0)
    a.daily_spend_eur = 10.0
    token = TokenState("M", liquidity_usd=100000)
    proposal = TradeProposal(Action.ENTER, "M", amount_eur=9.9)
    d = g.evaluate(
        proposal,
        a,
        token,
        features={
            "sellability_score": 1.0,
            "manipulation_risk": 0.0,
            "entry_validity": "VALID",
            "estimated_entry_fee_eur": 0.2,
        },
    )
    assert "MAX_DAILY_SPEND" in d.reasons
