from datetime import datetime, timezone

import pytest

from runner_genesis.ai_trader import Action, TradeProposal
from runner_genesis.config import Settings, ExecutionConfig, RiskConfig
from runner_genesis.domain.events import MarketEvent, EventType
from runner_genesis.domain.state import PaperAccount, TokenState
from runner_genesis.execution import PaperExecutionEngine
from runner_genesis.risk_governor import RiskGovernor


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_live_is_forbidden_in_config_and_assignment():
    with pytest.raises(ValueError):
        Settings(live_trading=True)
    with pytest.raises(ValueError):
        Settings(mode='LIVE')
    settings = Settings()
    with pytest.raises(ValueError):
        settings.live_trading = True
    assert not settings.live_trading


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1.0])
def test_nonfinite_or_negative_market_data_rejected(value):
    with pytest.raises(ValueError):
        MarketEvent(event_id='invalid', timestamp=T0, token_mint='M',
                    event_type=EventType.PRICE, price_usd=value)


def test_zero_sell_fraction_is_not_a_full_exit():
    engine = PaperExecutionEngine(ExecutionConfig(failed_tx_base_probability=0))
    fill = engine.execute(TradeProposal(Action.REDUCE, 'M', reduce_fraction=0),
                          TokenState('M', price_usd=1, liquidity_usd=100_000), T0, 10)
    assert fill is None


def test_kill_switch_stops_entries_but_allows_defensive_exit():
    risk = RiskGovernor(RiskConfig(kill_switch=True))
    token = TokenState('M', price_usd=1, liquidity_usd=100_000)
    account = PaperAccount(300, 300)
    assert not risk.evaluate(TradeProposal(Action.ENTER, 'M', amount_eur=10), account, token).approved
    assert risk.evaluate(TradeProposal(Action.EXIT, 'M', reduce_fraction=1), account, token).approved


def test_nonfinite_order_is_rejected():
    risk = RiskGovernor(RiskConfig())
    result = risk.evaluate(TradeProposal(Action.ENTER, 'M', amount_eur=float('nan')),
                           PaperAccount(300, 300), TokenState('M', liquidity_usd=100_000))
    assert 'INVALID_ORDER_SIZE' in result.reasons


def test_old_day_does_not_reset_daily_risk_counters():
    account = PaperAccount(300, 300)
    account.advance_accounting_day(T0.replace(day=2))
    account.daily_spend_eur = 50
    account.advance_accounting_day(T0)
    assert account.daily_spend_eur == 50
