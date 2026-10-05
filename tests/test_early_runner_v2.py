import pytest

from runner_genesis.engines.early_runner_v2 import (
    EarlyRunnerConfig,
    EarlyRunnerEventType,
    EarlyRunnerState,
    EarlyRunnerV2Engine,
)


def sample(ts, heat=90, buy=0.8, price=1.0, bid=0.999, ask=1.001, spread=20, depth=10_000, age=100, fresh=True, sanity=True, rejects=0, structure=None):
    row = {
        "type": "RADAR_SAMPLE",
        "heat": heat,
        "metrics": {
            "ts_ms": ts,
            "instrument": "TEST_USD",
            "price": price,
            "bid": bid,
            "ask": ask,
            "buy_ratio": buy,
            "spread_bps": spread,
            "book_total_usd": depth,
            "book_age_ms": age,
            "has_fresh_book": fresh,
            "price_sanity_ok": sanity,
            "price_sanity_rejections": rejects,
            "score": 42.0,
        },
    }
    if structure is not None:
        row["structure"] = structure
    return row


def test_shadow_only_is_hard_block():
    with pytest.raises(RuntimeError):
        EarlyRunnerV2Engine(EarlyRunnerConfig(shadow_only=False))


def test_detects_then_enters_when_execution_is_clean():
    e = EarlyRunnerV2Engine()
    events = e.process(sample(1_000))
    assert [x.event_type for x in events] == [EarlyRunnerEventType.CANDIDATE, EarlyRunnerEventType.ENTRY]
    assert e.state_for("TEST_USD")["state"] == EarlyRunnerState.IN_POSITION.value
    assert "ESPERANDO BUEN MOMENTO" in events[0].title
    assert "ENTRADA SIMULADA" in events[1].title


def test_waits_for_liquidity_instead_of_chasing():
    e = EarlyRunnerV2Engine()
    first = e.process(sample(1_000, spread=180, depth=2_000))
    assert [x.event_type for x in first] == [EarlyRunnerEventType.CANDIDATE]
    assert e.state_for("TEST_USD")["state"] == EarlyRunnerState.WAITING_ENTRY.value
    second = e.process(sample(61_000, spread=40, depth=12_000))
    assert [x.event_type for x in second] == [EarlyRunnerEventType.ENTRY]


def test_two_dead_samples_trigger_spanish_fast_exit():
    e = EarlyRunnerV2Engine()
    e.process(sample(1_000))
    assert not [x for x in e.process(sample(2_000, heat=20, buy=0.4, price=0.99, bid=0.989, ask=0.991)) if x.event_type == EarlyRunnerEventType.EXIT_INVALIDATION]
    out = e.process(sample(3_000, heat=20, buy=0.4, price=0.98, bid=0.979, ask=0.981))
    exits = [x for x in out if x.event_type == EarlyRunnerEventType.EXIT_INVALIDATION]
    assert len(exits) == 1
    assert "SALIDA RÁPIDA" in exits[0].title
    assert "impulso" in exits[0].message.lower()


def test_profit_protection_activates_and_exits_on_retrace():
    e = EarlyRunnerV2Engine(EarlyRunnerConfig(hold_message_interval_seconds=99999))
    e.process(sample(1_000))
    up = e.process(sample(11_000, price=1.06, bid=1.059, ask=1.061))
    assert any(x.event_type == EarlyRunnerEventType.PROTECTION_ENABLED for x in up)
    down = e.process(sample(21_000, price=1.025, bid=1.024, ask=1.026, heat=75, buy=0.65))
    assert any(x.event_type == EarlyRunnerEventType.EXIT_PROTECTION for x in down)


def test_no_development_exits_after_45_minutes():
    e = EarlyRunnerV2Engine(EarlyRunnerConfig(invalidation_consecutive_samples=99, hold_message_interval_seconds=99999))
    e.process(sample(1_000))
    out = e.process(sample(1_000 + 45 * 60 * 1000, heat=60, buy=0.6, price=1.005, bid=1.004, ask=1.006))
    assert any(x.event_type == EarlyRunnerEventType.EXIT_NO_DEVELOPMENT for x in out)


def test_extreme_sanity_rejections_go_to_quarantine():
    e = EarlyRunnerV2Engine()
    out = e.process(sample(1_000, rejects=6_000))
    assert [x.event_type for x in out] == [EarlyRunnerEventType.QUARANTINE]
    assert "CUARENTENA" in out[0].title


def test_extended_structure_is_not_chased():
    e = EarlyRunnerV2Engine()
    out = e.process(sample(1_000, structure={"entry_runner_phase": "EXTENDED", "entry_extension_score": 50}))
    assert [x.event_type for x in out] == [EarlyRunnerEventType.CANDIDATE_CANCELLED]
    assert "MOVIMIENTO DEMASIADO AVANZADO" in out[0].title
