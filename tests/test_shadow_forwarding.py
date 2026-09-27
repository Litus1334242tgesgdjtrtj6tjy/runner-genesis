from datetime import datetime, timezone

import httpx
import pytest

from runner_genesis.domain.events import EventType, MarketEvent
from runner_genesis.shadow import _post_event


@pytest.mark.asyncio
async def test_shadow_forwards_event_to_paper_api():
    seen = {}

    async def handler(request: httpx.Request):
        seen['path'] = request.url.path
        seen['body'] = request.content
        return httpx.Response(200, json={'snapshot': {'action': 'PASS'}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        event = MarketEvent(
            event_id='e1',
            timestamp=datetime.now(timezone.utc),
            token_mint='mint1',
            event_type=EventType.BUY,
            asset_match_verified=True,
        )
        out = await _post_event(client, 'http://paper.local', event)

    assert seen['path'] == '/api/event'
    assert b'"token_mint":"mint1"' in seen['body']
    assert out['snapshot']['action'] == 'PASS'
