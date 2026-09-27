from __future__ import annotations
from typing import Protocol, Iterable
from datetime import datetime

class WalletDataProvider(Protocol):
    def wallet_snapshot(self, wallet: str, as_of: datetime) -> dict | None: ...

class PumpLeaderboardProvider(Protocol):
    def snapshots(self, as_of: datetime) -> Iterable[dict]: ...

class TransactionProvider(Protocol):
    def transactions(self, address: str, before: datetime | None = None) -> Iterable[dict]: ...

class PriceProvider(Protocol):
    def price(self, mint: str, as_of: datetime | None = None) -> dict | None: ...

class TokenMetadataProvider(Protocol):
    def token_metadata(self, mint: str) -> dict | None: ...

class SocialDiscoveryProvider(Protocol):
    def observations(self, mint: str, as_of: datetime) -> Iterable[dict]: ...

class FomoDiscoveryProvider(Protocol):
    def observations(self, mint: str, as_of: datetime) -> Iterable[dict]: ...
