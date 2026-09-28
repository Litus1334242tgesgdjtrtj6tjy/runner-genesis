from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar, Iterable

T = TypeVar("T")

class FutureLeakageError(RuntimeError):
    pass

@dataclass(order=True)
class VersionedValue(Generic[T]):
    available_at: datetime
    value: T

class PointInTimeSeries(Generic[T]):
    """Stores values by *availability* time, not by eventual outcome time."""
    def __init__(self) -> None:
        self._items: list[VersionedValue[T]] = []

    def add(self, available_at: datetime, value: T) -> None:
        if self._items and available_at < self._items[-1].available_at:
            # preserve strict chronological reproducibility
            raise ValueError("PointInTimeSeries additions must be chronological")
        self._items.append(VersionedValue(available_at, value))

    def values_as_of(self, as_of: datetime) -> list[T]:
        idx = bisect_right([x.available_at for x in self._items], as_of)
        return [x.value for x in self._items[:idx]]

    def latest_as_of(self, as_of: datetime) -> T | None:
        vals = self.values_as_of(as_of)
        return vals[-1] if vals else None

    def assert_available(self, available_at: datetime, decision_time: datetime) -> None:
        if available_at > decision_time:
            raise FutureLeakageError(f"value available at {available_at.isoformat()} after decision {decision_time.isoformat()}")
