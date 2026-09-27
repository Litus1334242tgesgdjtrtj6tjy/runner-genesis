from datetime import datetime, timezone

from runner_genesis.config import Settings
from runner_genesis.db import RuntimeRepository
from runner_genesis.orchestrator import RunnerGenesisOmega


def test_smart_position_and_token_state_restore(tmp_path):
    url = f"sqlite:///{tmp_path / 'smart.db'}"
    repo = RuntimeRepository(url)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    repo.record_wallet_position(
        "W_A", "M_A", t0,
        {
            "first_entry_time": t0,
            "last_entry_time": t0,
            "last_activity_time": t0,
            "average_entry_price": 1.25,
            "bought_token": 100.0,
            "sold_token": 20.0,
            "bought_usd": 125.0,
            "sold_usd": 25.0,
            "buy_count": 2,
            "sell_count": 1,
            "state": "REDUCE",
            "buy_sizes_usd": [50.0, 75.0],
            "event_ids": ["e1", "e2", "e3"],
        },
    )
    repo.record_smart_state("M_A", t0, {"smart_capital_state": "PERSISTENCE"})

    settings = Settings(database_url=url)
    settings.features["database_persistence"] = {"enabled": True}
    engine = RunnerGenesisOmega(settings)

    pos = engine.smart.positions[("W_A", "M_A")]
    assert pos.buy_count == 2
    assert pos.sell_count == 1
    assert abs(pos.retained_fraction - 0.8) < 1e-9
    assert abs(pos.average_entry_price - 1.25) < 1e-9
    assert engine.smart.token_state["M_A"] == "PERSISTENCE"
