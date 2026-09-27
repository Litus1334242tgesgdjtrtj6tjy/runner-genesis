import pytest
import httpx

from runner_genesis.research_sources import FomoScanPumpProvider


class FakeAsyncClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None, params=None):
        FakeAsyncClient.calls += 1
        request = httpx.Request("GET", url)
        if FakeAsyncClient.calls == 1:
            return httpx.Response(429, headers={"retry-after": "0.1"}, json={"error": "rate"}, request=request)
        return httpx.Response(
            200,
            json={"data": [{"wallet": "W1", "rank": 1}], "meta": {"asOf": "2026-09-27T18:00:00Z"}},
            request=request,
        )


@pytest.mark.asyncio
async def test_fomoscan_retries_429_then_succeeds(monkeypatch):
    FakeAsyncClient.calls = 0

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("runner_genesis.research_sources.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("runner_genesis.research_sources.asyncio.sleep", no_sleep)

    provider = FomoScanPumpProvider("test-key", max_retries=2)
    rows, observed_at = await provider.pump_leaderboard()

    assert FakeAsyncClient.calls == 2
    assert len(rows) == 1
    assert rows[0]["wallet_address"] == "W1"
    assert rows[0]["rank"] == 1
    assert observed_at.year == 2026
