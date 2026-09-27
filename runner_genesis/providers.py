from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterable


class WalletDataProvider(ABC):
    @abstractmethod
    async def wallet_history(self, wallet: str, before: datetime | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError


class PumpLeaderboardProvider(ABC):
    @abstractmethod
    async def snapshot(self, observed_at: datetime) -> list[dict[str, Any]]:
        raise NotImplementedError


class TransactionProvider(ABC):
    @abstractmethod
    async def transactions(self, address: str, before: datetime | None = None) -> Iterable[dict[str, Any]]:
        raise NotImplementedError


class PriceProvider(ABC):
    @abstractmethod
    async def price(self, mint: str, at: datetime | None = None) -> dict[str, Any] | None:
        raise NotImplementedError


class TokenMetadataProvider(ABC):
    @abstractmethod
    async def metadata(self, mint: str, at: datetime | None = None) -> dict[str, Any] | None:
        raise NotImplementedError


class SocialDiscoveryProvider(ABC):
    @abstractmethod
    async def observations(self, mint: str, since: datetime) -> list[dict[str, Any]]:
        raise NotImplementedError


class FomoDiscoveryProvider(SocialDiscoveryProvider):
    pass


class MiroFishRolloutProvider(ABC):
    @abstractmethod
    def rollouts(self, mint: str, decision_time: datetime, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
