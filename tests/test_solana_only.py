from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from runner_genesis.config import Settings
from runner_genesis.domain.events import EventType, MarketEvent


def test_settings_are_solana_only():
    assert Settings().network == "solana"
    with pytest.raises(ValidationError, match="Solana only"):
        Settings(network="ethereum")


def test_market_events_reject_non_solana_chain():
    with pytest.raises(ValidationError, match="only Solana"):
        MarketEvent(
            event_id="eth-event",
            timestamp=datetime.now(timezone.utc),
            token_mint="0xdeadbeef",
            chain="ethereum",
            event_type=EventType.PRICE,
        )


def test_market_events_default_to_solana():
    event = MarketEvent(
        event_id="sol-event",
        timestamp=datetime.now(timezone.utc),
        token_mint="DemoMint",
        event_type=EventType.PRICE,
    )
    assert event.chain == "solana"
