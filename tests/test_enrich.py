from datetime import datetime, timezone

import pytest

from runner_genesis.domain.events import EventType, MarketEvent
from runner_genesis.ingestion.enrich import DexScreenerEnricher


@pytest.mark.asyncio
async def test_enricher_skips_market_lookup_when_verified_quote_is_complete(monkeypatch):
    enricher = DexScreenerEnricher()

    async def should_not_call(_mint):
        raise AssertionError("unexpected market lookup")

    monkeypatch.setattr(enricher, "_pairs", should_not_call)
    event = MarketEvent(
        event_id="complete",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        token_mint="MINT",
        event_type=EventType.PRICE,
        price_usd=1.0,
        market_cap_usd=100_000,
        liquidity_usd=50_000,
        asset_match_verified=True,
    )
    out = await enricher.enrich(event)
    assert out.price_usd == 1.0
    assert "market_enrichment_error" not in out.metadata
    await enricher.aclose()


@pytest.mark.asyncio
async def test_enricher_preserves_exact_mint_identity(monkeypatch):
    enricher = DexScreenerEnricher()

    async def fake_pairs(_mint):
        return [
            {
                "chainId": "solana",
                "baseToken": {"address": "MINT"},
                "priceUsd": "2.0",
                "marketCap": 200_000,
                "liquidity": {"usd": 80_000},
                "pairAddress": "PAIR",
                "dexId": "pumpfun",
            }
        ]

    monkeypatch.setattr(enricher, "_pairs", fake_pairs)
    event = MarketEvent(
        event_id="missing-market",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        token_mint="MINT",
        event_type=EventType.PRICE,
        asset_match_verified=True,
    )
    out = await enricher.enrich(event)
    assert out.price_usd == 2.0
    assert out.market_cap_usd == 200_000
    assert out.liquidity_usd == 80_000
    assert out.metadata["dexscreener_pair"] == "PAIR"
    await enricher.aclose()
