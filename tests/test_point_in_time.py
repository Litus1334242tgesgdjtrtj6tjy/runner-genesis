from datetime import datetime, timezone, timedelta
import pytest
from runner_genesis.point_in_time import PointInTimeSeries, FutureLeakageError

def test_as_of_excludes_future():
    s=PointInTimeSeries[int]()
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    s.add(t,1); s.add(t+timedelta(seconds=10),2)
    assert s.values_as_of(t+timedelta(seconds=5)) == [1]

def test_future_leakage_guard():
    s=PointInTimeSeries[int]()
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    with pytest.raises(FutureLeakageError):
        s.assert_available(t+timedelta(seconds=1),t)
