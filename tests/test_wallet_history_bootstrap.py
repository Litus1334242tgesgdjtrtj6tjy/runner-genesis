from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from runner_genesis.config import Settings, PumpDiscoveryConfig
from runner_genesis.engines.actor_graph import ActorGraphEngine
from runner_genesis.engines.discovery import PumpDiscoveryEngine
from runner_genesis.ingestion.helius_history import HeliusWalletHistoryClient
from runner_genesis.research_sources import WalletResearchBackfillService
from runner_genesis.research_sync import ResearchSyncCoordinator
from runner_genesis.state_store import MarketStateStore


class _Response:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _PagedAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        params = dict(params or {})
        self.__class__.calls.append(params)
        before = params.get("before")
        if before is None:
            return _Response([
                {"signature": "s1", "timestamp": 1000},
                {"signature": "s2", "timestamp": 900},
            ])
        if before == "s2":
            return _Response([
                {"signature": "s3", "timestamp": 800},
                {"signature": "s4", "timestamp": 700},
            ])
        return _Response([
            {"signature": "unexpected", "timestamp": 600},
        ])


@pytest.mark.asyncio
async def test_helius_pagination_stops_once_lookback_cutoff_is_reached(monkeypatch):
    _PagedAsyncClient.calls = []
    monkeypatch.setattr(
        "runner_genesis.ingestion.helius_history.httpx.AsyncClient",
        _PagedAsyncClient,
    )
    client = HeliusWalletHistoryClient("test")
    cutoff = datetime.fromtimestamp(750, tz=timezone.utc)
    rows = await client.fetch_transactions(
        "WALLET",
        limit=2,
        max_pages=5,
        stop_before_time=cutoff,
    )
    assert [x["signature"] for x in rows] == ["s1", "s2", "s3", "s4"]
    assert len(_PagedAsyncClient.calls) == 2
    assert _PagedAsyncClient.calls[1]["before"] == "s2"


class _BundleClient:
    def __init__(self, rows):
        self.rows = rows
        self.kwargs = None

    async def fetch_transactions(self, wallet, **kwargs):
        self.kwargs = kwargs
        return list(self.rows)


@pytest.mark.asyncio
async def test_short_wallet_history_counts_as_complete_even_if_account_is_newer_than_30d():
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    client = _BundleClient([
        {
            "type": "TRANSFER",
            "signature": "only-tx",
            "timestamp": int((now - timedelta(days=5)).timestamp()),
            "nativeTransfers": [],
        }
    ])
    service = WalletResearchBackfillService(client)
    bundle = await service.fetch_wallet_bundle(
        "W",
        limit=100,
        max_pages=10,
        stop_before_time=now - timedelta(days=30),
    )
    assert bundle.history_exhausted is True
    result = service.apply_bundle(
        bundle,
        MarketStateStore(),
        ActorGraphEngine(),
    )
    assert result.history_target_reached is True
    assert result.history_exhausted is True
    assert result.next_before_signature is None


@pytest.mark.asyncio
async def test_full_page_newer_than_cutoff_emits_continuation_cursor():
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    client = _BundleClient([
        {"type": "TRANSFER", "signature": "newer-1", "timestamp": int((now - timedelta(days=1)).timestamp()), "nativeTransfers": []},
        {"type": "TRANSFER", "signature": "newer-2", "timestamp": int((now - timedelta(days=2)).timestamp()), "nativeTransfers": []},
    ])
    service = WalletResearchBackfillService(client)
    bundle = await service.fetch_wallet_bundle(
        "W",
        limit=2,
        max_pages=1,
        stop_before_time=now - timedelta(days=30),
        before="previous-page",
    )
    assert client.kwargs["before"] == "previous-page"
    assert bundle.history_exhausted is False
    result = service.apply_bundle(bundle, MarketStateStore(), ActorGraphEngine())
    assert result.history_target_reached is False
    assert result.next_before_signature == "newer-2"


class _BackfillRepo:
    def load_wallet_backfill_status(self, limit=100_000):
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        return [
            {
                "wallet_address": "INCOMPLETE",
                "last_success_at": now,
                "payload": {
                    "history_target_reached": False,
                    "next_before_signature": "cursor-123",
                },
            },
            {
                "wallet_address": "COMPLETE",
                "last_success_at": now,
                "payload": {
                    "history_target_reached": True,
                    "next_before_signature": None,
                },
            },
        ]


def test_bootstrap_cursor_hydrates_and_uses_shorter_cooldown():
    settings = Settings(helius_api_key="test")
    settings.helius_history.bootstrap_refresh_seconds = 1800
    settings.helius_history.refresh_seconds = 21600
    engine = SimpleNamespace(
        repository=_BackfillRepo(),
        discovery=PumpDiscoveryEngine(PumpDiscoveryConfig()),
    )
    coordinator = ResearchSyncCoordinator(settings, engine)

    assert coordinator._history_cursor["INCOMPLETE"] == "cursor-123"
    assert "COMPLETE" in coordinator._history_target_reached

    base = datetime(2026, 1, 31, tzinfo=timezone.utc)
    assert coordinator._wallet_backfill_due("INCOMPLETE", base + timedelta(minutes=31))
    assert not coordinator._wallet_backfill_due("COMPLETE", base + timedelta(minutes=31))
    assert coordinator._wallet_backfill_due("COMPLETE", base + timedelta(hours=6))
