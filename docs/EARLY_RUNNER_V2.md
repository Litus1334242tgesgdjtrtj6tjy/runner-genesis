# EARLY_RUNNER_V2 — SHADOW/PAPER

## Objective

Implement the architecture derived from Flight Recorder + Flexible Shadow + Preconfirm Shadow + Progressive Shadow:

**early detection -> anti-chase context -> wait for executable liquidity -> short PAPER position management -> Spanish Telegram messages**.

The detector is intentionally separated from the old DEEP/STRICT/FAST hard-entry path. Those fields may still be recorded as context, but they do not block early detection.

## Safety

- SHADOW/PAPER only.
- The engine raises if shadow_only=false.
- No exchange calls and no live orders.
- Experimental branch only until a larger untouched out-of-sample sample validates the numerical thresholds.

## Default state machine

1. IDLE: no candidate.
2. WAITING_ENTRY: possible runner detected; wait for a clean executable window instead of chasing.
3. IN_POSITION: PAPER entry uses observed ask and exits use observed bid.
4. COOLDOWN: prevents immediate re-entry.
5. QUARANTINE: data quality is too degraded.

## Detector

Default candidate:
- heat >= 80
- buy_ratio >= 0.70
- price_sanity_ok = true
- price_sanity_rejections < 5000

No mandatory deep_baseline_ready, full STRICT, or fixed FAST pass ratio.

## Anti-chase

When structure data exists:
- block entry_runner_phase=EXTENDED
- block ESTABLISHED_RUNNER when entry_extension_score >= 35

Missing structure does not reject a candidate.

## Wait for execution

A detection is not an automatic buy. The default wait is up to 180 seconds for:
- heat >= 50
- buy_ratio >= 0.60
- spread <= 100 bps
- fresh order book
- book age <= 1800 ms
- book depth >= 6000 USD
- valid ask

If the impulse dies before execution quality improves, the candidate is cancelled.

## Position horizon

Working horizon: minutes to about one hour.

User-facing exits:
- 🚨 SALIDA RÁPIDA — EL IMPULSO SE HA DEBILITADO
- 🛡️ PROTECCIÓN DE BENEFICIO ACTIVADA
- 💰 SALIDA — SE PROTEGE EL BENEFICIO CONSEGUIDO
- ⏱️ SALIDA POR FALTA DE DESARROLLO
- ⏰ SALIDA — LÍMITE DE TIEMPO ALCANZADO

While the setup remains strong:
- 🟢 MANTENER — EL MOVIMIENTO SIGUE FUERTE

## Telegram

runner_genesis/telegram_notifier.py can send the Spanish event text using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID. Real secrets must stay in the local environment; an empty example file is provided.

The live-tail SHADOW watcher is scripts/run_early_runner_v2_shadow.py. It tails flight_*.jsonl files, passes RADAR_SAMPLE rows through the state machine and sends only state/action events, avoiding one Telegram message per radar sample.

## Replay

Use scripts/replay_early_runner_v2.py to replay existing Flight Recorder JSONL and write early_runner_v2_events.jsonl for audit/backtest.

## Important

The architecture is the current freeze. Exact numerical exit thresholds are candidate SHADOW parameters, not production-proven constants. They must be re-estimated only after accumulating new untouched observations.
