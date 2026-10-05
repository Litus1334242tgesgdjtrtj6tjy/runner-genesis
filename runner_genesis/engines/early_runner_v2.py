from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import Any


class EarlyRunnerState(StrEnum):
    IDLE = "IDLE"
    WAITING_ENTRY = "WAITING_ENTRY"
    IN_POSITION = "IN_POSITION"
    COOLDOWN = "COOLDOWN"
    QUARANTINE = "QUARANTINE"


class EarlyRunnerEventType(StrEnum):
    CANDIDATE = "CANDIDATE"
    ENTRY = "ENTRY"
    HOLD = "HOLD"
    PROTECTION_ENABLED = "PROTECTION_ENABLED"
    PROTECTION_RAISED = "PROTECTION_RAISED"
    EXIT_INVALIDATION = "EXIT_INVALIDATION"
    EXIT_PROTECTION = "EXIT_PROTECTION"
    EXIT_NO_DEVELOPMENT = "EXIT_NO_DEVELOPMENT"
    EXIT_TIME_LIMIT = "EXIT_TIME_LIMIT"
    CANDIDATE_EXPIRED = "CANDIDATE_EXPIRED"
    CANDIDATE_CANCELLED = "CANDIDATE_CANCELLED"
    QUARANTINE = "QUARANTINE"


@dataclass(slots=True)
class EarlyRunnerConfig:
    """Candidate configuration for SHADOW/PAPER validation only.

    These defaults encode the qualitative findings from Flight Recorder + shadow
    experiments. They are deliberately conservative and MUST NOT be treated as
    production-optimized constants until a larger out-of-sample sample exists.
    """

    shadow_only: bool = True

    detector_heat_min: float = 80.0
    detector_heat_high: float = 99.0
    detector_buy_ratio_min: float = 0.70

    sanity_rejections_quarantine: int = 5000

    blocked_runner_phases: tuple[str, ...] = ("EXTENDED",)
    established_runner_extension_block: float = 35.0

    entry_wait_max_seconds: float = 180.0
    entry_heat_floor: float = 50.0
    entry_buy_ratio_floor: float = 0.60
    max_spread_bps: float = 100.0
    max_book_age_ms: float = 1800.0
    min_book_total_usd: float = 6000.0

    invalidation_heat_max: float = 35.0
    invalidation_buy_ratio_max: float = 0.50
    invalidation_consecutive_samples: int = 2
    no_development_seconds: float = 45.0 * 60.0
    max_position_seconds: float = 60.0 * 60.0
    no_development_mfe_pct: float = 2.0

    protection_activation_mfe_pct: float = 2.0
    protection_retrace_fraction: float = 0.40
    protection_min_locked_pct: float = 0.50
    protection_raise_step_pct: float = 0.50

    hold_message_interval_seconds: float = 10.0 * 60.0
    cooldown_seconds: float = 10.0 * 60.0

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "EarlyRunnerConfig":
        raw = dict(raw or {})
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in raw.items() if k in allowed}
        if "blocked_runner_phases" in cleaned and isinstance(cleaned["blocked_runner_phases"], list):
            cleaned["blocked_runner_phases"] = tuple(str(x) for x in cleaned["blocked_runner_phases"])
        return cls(**cleaned)


@dataclass(slots=True)
class EarlyRunnerEvent:
    event_type: EarlyRunnerEventType
    ts_ms: int
    instrument: str
    title: str
    message: str
    state: EarlyRunnerState
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["event_type"] = self.event_type.value
        out["state"] = self.state.value
        return out

    @property
    def telegram_text(self) -> str:
        return f"{self.title}\n{self.message}"


@dataclass(slots=True)
class _InstrumentState:
    state: EarlyRunnerState = EarlyRunnerState.IDLE
    detected_at_ms: int | None = None
    entered_at_ms: int | None = None
    cooldown_until_ms: int = 0
    entry_price: float | None = None
    peak_price: float | None = None
    peak_pnl_pct: float = 0.0
    protection_floor_pct: float | None = None
    last_hold_message_ms: int = 0
    invalidation_count: int = 0
    last_heat: float = 0.0
    last_buy_ratio: float = 0.5


class EarlyRunnerV2Engine:
    """Early detector -> executable entry -> short PAPER position manager."""

    def __init__(self, cfg: EarlyRunnerConfig | None = None) -> None:
        self.cfg = cfg or EarlyRunnerConfig()
        if not self.cfg.shadow_only:
            raise RuntimeError("EARLY_RUNNER_V2 solo puede ejecutarse en SHADOW/PAPER")
        self._states: dict[str, _InstrumentState] = {}

    @staticmethod
    def _num(value: Any, default: float = 0.0) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return default
        if v != v or v in (float("inf"), float("-inf")):
            return default
        return v

    @staticmethod
    def _bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "si", "sí"}
        return bool(value)

    def state_for(self, instrument: str) -> dict[str, Any]:
        s = self._states.get(instrument, _InstrumentState())
        out = asdict(s)
        out["state"] = s.state.value
        return out

    def _unpack(self, sample: dict[str, Any]) -> dict[str, Any]:
        metrics = sample.get("metrics") if isinstance(sample.get("metrics"), dict) else sample
        structure = sample.get("structure") if isinstance(sample.get("structure"), dict) else {}
        fast = sample.get("fast") if isinstance(sample.get("fast"), dict) else {}
        strict = sample.get("strict") if isinstance(sample.get("strict"), dict) else {}
        ts_ms = int(self._num(metrics.get("ts_ms", sample.get("ts_ms", 0)), 0.0))
        instrument = str(metrics.get("instrument") or sample.get("instrument") or "").strip()
        return {
            "ts_ms": ts_ms,
            "instrument": instrument,
            "price": self._num(metrics.get("price"), 0.0),
            "bid": self._num(metrics.get("bid"), 0.0),
            "ask": self._num(metrics.get("ask"), 0.0),
            "heat": self._num(sample.get("heat", metrics.get("heat")), 0.0),
            "buy_ratio": self._num(metrics.get("buy_ratio"), 0.5),
            "spread_bps": self._num(metrics.get("spread_bps"), 1e9),
            "book_total_usd": self._num(metrics.get("book_total_usd"), 0.0),
            "book_age_ms": self._num(metrics.get("book_age_ms"), 1e12),
            "has_fresh_book": self._bool(metrics.get("has_fresh_book"), False),
            "price_sanity_ok": self._bool(metrics.get("price_sanity_ok"), True),
            "price_sanity_rejections": int(self._num(metrics.get("price_sanity_rejections"), 0.0)),
            "score": self._num(metrics.get("score"), 0.0),
            "fast_pass_ratio": self._num(fast.get("pass_ratio"), 0.0),
            "strict_pass_ratio": self._num(strict.get("pass_ratio"), 0.0),
            "entry_runner_phase": str(structure.get("entry_runner_phase") or "").upper(),
            "structure_state": str(structure.get("structure_state") or "").upper(),
            "entry_extension_score": self._num(structure.get("entry_extension_score"), 0.0),
        }

    def _anti_chase_blocked(self, x: dict[str, Any]) -> tuple[bool, str | None]:
        phase = x["entry_runner_phase"]
        state = x["structure_state"]
        ext = x["entry_extension_score"]
        if phase and phase in {p.upper() for p in self.cfg.blocked_runner_phases}:
            return True, f"fase {phase} demasiado extendida"
        if state == "ESTABLISHED_RUNNER" and ext >= self.cfg.established_runner_extension_block:
            return True, f"runner ya establecido con extensión {ext:.1f}"
        return False, None

    def _quarantine_reason(self, x: dict[str, Any]) -> str | None:
        if not x["price_sanity_ok"]:
            return "el control de calidad del precio no es fiable"
        if x["price_sanity_rejections"] >= self.cfg.sanity_rejections_quarantine:
            return f"demasiados rechazos de precio ({x['price_sanity_rejections']})"
        if x["price"] <= 0:
            return "precio no válido"
        return None

    def _detector_ready(self, x: dict[str, Any]) -> bool:
        return x["heat"] >= self.cfg.detector_heat_min and x["buy_ratio"] >= self.cfg.detector_buy_ratio_min

    def _execution_ready(self, x: dict[str, Any]) -> tuple[bool, list[str]]:
        failed: list[str] = []
        if x["heat"] < self.cfg.entry_heat_floor:
            failed.append("el impulso se ha enfriado")
        if x["buy_ratio"] < self.cfg.entry_buy_ratio_floor:
            failed.append("la presión compradora es insuficiente")
        if x["spread_bps"] > self.cfg.max_spread_bps:
            failed.append("el diferencial de compra/venta es demasiado amplio")
        if not x["has_fresh_book"]:
            failed.append("el libro de órdenes no está actualizado")
        if x["book_age_ms"] > self.cfg.max_book_age_ms:
            failed.append("el libro de órdenes es demasiado antiguo")
        if x["book_total_usd"] < self.cfg.min_book_total_usd:
            failed.append("hay poca profundidad disponible para ejecutar")
        if x["ask"] <= 0:
            failed.append("no hay precio de compra válido")
        return not failed, failed

    @staticmethod
    def _pct(current: float, entry: float) -> float:
        if entry <= 0:
            return 0.0
        return (current / entry - 1.0) * 100.0

    def _reset_to_cooldown(self, s: _InstrumentState, ts_ms: int) -> None:
        s.state = EarlyRunnerState.COOLDOWN
        s.cooldown_until_ms = ts_ms + int(self.cfg.cooldown_seconds * 1000)
        s.detected_at_ms = None
        s.entered_at_ms = None
        s.entry_price = None
        s.peak_price = None
        s.peak_pnl_pct = 0.0
        s.protection_floor_pct = None
        s.invalidation_count = 0
        s.last_hold_message_ms = 0

    def process(self, sample: dict[str, Any]) -> list[EarlyRunnerEvent]:
        x = self._unpack(sample)
        ts_ms = x["ts_ms"]
        instrument = x["instrument"]
        if not instrument or ts_ms <= 0:
            return []

        s = self._states.setdefault(instrument, _InstrumentState())
        s.last_heat = x["heat"]
        s.last_buy_ratio = x["buy_ratio"]
        events: list[EarlyRunnerEvent] = []

        if s.state == EarlyRunnerState.COOLDOWN:
            if ts_ms < s.cooldown_until_ms:
                return []
            s.state = EarlyRunnerState.IDLE

        quarantine = self._quarantine_reason(x)
        if quarantine:
            if s.state != EarlyRunnerState.QUARANTINE:
                s.state = EarlyRunnerState.QUARANTINE
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.QUARANTINE, ts_ms, instrument,
                    "⚠️ DATOS EN CUARENTENA",
                    f"{instrument}: no se tomará una entrada porque {quarantine}.",
                    s.state,
                    {"reason": quarantine, "price_sanity_rejections": x["price_sanity_rejections"]},
                ))
            return events
        elif s.state == EarlyRunnerState.QUARANTINE:
            s.state = EarlyRunnerState.IDLE

        if s.state == EarlyRunnerState.IDLE:
            if not self._detector_ready(x):
                return []
            blocked, reason = self._anti_chase_blocked(x)
            if blocked:
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.CANDIDATE_CANCELLED, ts_ms, instrument,
                    "⛔ CANDIDATO DESCARTADO — MOVIMIENTO DEMASIADO AVANZADO",
                    f"{instrument}: se detectó fuerza, pero no se persigue la entrada porque {reason}.",
                    s.state,
                    {"reason": reason, "heat": x["heat"], "buy_ratio": x["buy_ratio"]},
                ))
                s.cooldown_until_ms = ts_ms + int(self.cfg.cooldown_seconds * 1000)
                s.state = EarlyRunnerState.COOLDOWN
                return events

            s.state = EarlyRunnerState.WAITING_ENTRY
            s.detected_at_ms = ts_ms
            events.append(EarlyRunnerEvent(
                EarlyRunnerEventType.CANDIDATE, ts_ms, instrument,
                "👀 POSIBLE RUNNER DETECTADO — ESPERANDO BUEN MOMENTO DE ENTRADA",
                f"{instrument}: hay una señal temprana. Todavía no se entra. Impulso {x['heat']:.1f}, "
                f"presión compradora {x['buy_ratio']:.0%}. El motor espera que el precio y la liquidez "
                "permitan comprar sin perseguir el movimiento.",
                s.state,
                {"heat": x["heat"], "buy_ratio": x["buy_ratio"], "score": x["score"]},
            ))

        if s.state == EarlyRunnerState.WAITING_ENTRY:
            assert s.detected_at_ms is not None
            wait_s = max(0.0, (ts_ms - s.detected_at_ms) / 1000.0)
            if wait_s > self.cfg.entry_wait_max_seconds:
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.CANDIDATE_EXPIRED, ts_ms, instrument,
                    "⌛ CANDIDATO DESCARTADO — NO APARECIÓ UNA BUENA ENTRADA",
                    f"{instrument}: la señal se vigiló durante {wait_s/60:.1f} min, pero no apareció "
                    "una ventana de compra suficientemente limpia. No se entra.",
                    s.state,
                    {"wait_seconds": wait_s},
                ))
                self._reset_to_cooldown(s, ts_ms)
                return events

            if x["heat"] < self.cfg.invalidation_heat_max and x["buy_ratio"] < self.cfg.invalidation_buy_ratio_max:
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.CANDIDATE_CANCELLED, ts_ms, instrument,
                    "❌ CANDIDATO CANCELADO — EL IMPULSO SE HA APAGADO ANTES DE ENTRAR",
                    f"{instrument}: la señal temprana perdió fuerza antes de encontrar una compra aceptable. No se entra.",
                    s.state,
                    {"heat": x["heat"], "buy_ratio": x["buy_ratio"]},
                ))
                self._reset_to_cooldown(s, ts_ms)
                return events

            ready, failed = self._execution_ready(x)
            if ready:
                s.state = EarlyRunnerState.IN_POSITION
                s.entered_at_ms = ts_ms
                s.entry_price = x["ask"]
                s.peak_price = x["ask"]
                s.peak_pnl_pct = 0.0
                s.invalidation_count = 0
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.ENTRY, ts_ms, instrument,
                    "🟢 ENTRADA SIMULADA — CONDICIONES DE COMPRA ACEPTABLES",
                    f"{instrument}: el posible runner sigue activo y la ejecución ha mejorado. "
                    f"Entrada PAPER estimada a {x['ask']:.10g}. Diferencial {x['spread_bps']:.1f} bps, "
                    f"profundidad {x['book_total_usd']:.0f} USD.",
                    s.state,
                    {
                        "entry_price": s.entry_price,
                        "heat": x["heat"],
                        "buy_ratio": x["buy_ratio"],
                        "spread_bps": x["spread_bps"],
                        "book_total_usd": x["book_total_usd"],
                        "wait_seconds": wait_s,
                        "execution_failed_reasons": failed,
                    },
                ))
                return events

        if s.state != EarlyRunnerState.IN_POSITION:
            return events

        assert s.entry_price is not None and s.entered_at_ms is not None
        exit_price = x["bid"] if x["bid"] > 0 else x["price"]
        if exit_price <= 0:
            return events

        pnl_pct = self._pct(exit_price, s.entry_price)
        if s.peak_price is None or exit_price > s.peak_price:
            s.peak_price = exit_price
        s.peak_pnl_pct = max(s.peak_pnl_pct, self._pct(s.peak_price, s.entry_price))
        held_s = max(0.0, (ts_ms - s.entered_at_ms) / 1000.0)

        if x["heat"] <= self.cfg.invalidation_heat_max and x["buy_ratio"] <= self.cfg.invalidation_buy_ratio_max:
            s.invalidation_count += 1
        else:
            s.invalidation_count = 0
        if s.invalidation_count >= max(1, self.cfg.invalidation_consecutive_samples):
            events.append(EarlyRunnerEvent(
                EarlyRunnerEventType.EXIT_INVALIDATION, ts_ms, instrument,
                "🚨 SALIDA RÁPIDA — EL IMPULSO SE HA DEBILITADO",
                f"{instrument}: ha desaparecido el impulso que justificó la entrada. "
                f"Resultado PAPER aproximado {pnl_pct:+.2f}%. Se recomienda cerrar la posición.",
                s.state,
                {"pnl_pct": pnl_pct, "held_seconds": held_s, "heat": x["heat"], "buy_ratio": x["buy_ratio"]},
            ))
            self._reset_to_cooldown(s, ts_ms)
            return events

        if s.peak_pnl_pct >= self.cfg.protection_activation_mfe_pct:
            candidate_floor = max(
                self.cfg.protection_min_locked_pct,
                s.peak_pnl_pct * (1.0 - self.cfg.protection_retrace_fraction),
            )
            if s.protection_floor_pct is None:
                s.protection_floor_pct = candidate_floor
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.PROTECTION_ENABLED, ts_ms, instrument,
                    "🛡️ PROTECCIÓN DE BENEFICIO ACTIVADA",
                    f"{instrument}: la operación ya ha avanzado {s.peak_pnl_pct:+.2f}% desde la entrada. "
                    f"A partir de ahora se protege aproximadamente un beneficio de {s.protection_floor_pct:+.2f}% "
                    "si el precio se gira.",
                    s.state,
                    {"pnl_pct": pnl_pct, "peak_pnl_pct": s.peak_pnl_pct, "protection_floor_pct": s.protection_floor_pct},
                ))
            elif candidate_floor >= s.protection_floor_pct + self.cfg.protection_raise_step_pct:
                s.protection_floor_pct = candidate_floor
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.PROTECTION_RAISED, ts_ms, instrument,
                    "🔒 SE SUBE LA PROTECCIÓN DEL BENEFICIO",
                    f"{instrument}: el runner ha seguido avanzando. Máximo desde entrada {s.peak_pnl_pct:+.2f}%. "
                    f"El beneficio protegido sube aproximadamente a {s.protection_floor_pct:+.2f}%.",
                    s.state,
                    {"pnl_pct": pnl_pct, "peak_pnl_pct": s.peak_pnl_pct, "protection_floor_pct": s.protection_floor_pct},
                ))

            if s.protection_floor_pct is not None and pnl_pct <= s.protection_floor_pct:
                events.append(EarlyRunnerEvent(
                    EarlyRunnerEventType.EXIT_PROTECTION, ts_ms, instrument,
                    "💰 SALIDA — SE PROTEGE EL BENEFICIO CONSEGUIDO",
                    f"{instrument}: el precio ha retrocedido después de alcanzar un máximo de {s.peak_pnl_pct:+.2f}%. "
                    f"Resultado PAPER aproximado {pnl_pct:+.2f}%. Se recomienda cerrar para no devolver una parte "
                    "importante del avance.",
                    s.state,
                    {"pnl_pct": pnl_pct, "peak_pnl_pct": s.peak_pnl_pct, "protection_floor_pct": s.protection_floor_pct},
                ))
                self._reset_to_cooldown(s, ts_ms)
                return events

        if held_s >= self.cfg.no_development_seconds and s.peak_pnl_pct < self.cfg.no_development_mfe_pct:
            events.append(EarlyRunnerEvent(
                EarlyRunnerEventType.EXIT_NO_DEVELOPMENT, ts_ms, instrument,
                "⏱️ SALIDA POR FALTA DE DESARROLLO",
                f"{instrument}: han pasado {held_s/60:.0f} minutos y el movimiento esperado no se ha desarrollado. "
                f"El mejor avance fue {s.peak_pnl_pct:+.2f}% y el resultado actual es {pnl_pct:+.2f}%. "
                "Se recomienda cerrar y liberar el capital.",
                s.state,
                {"pnl_pct": pnl_pct, "peak_pnl_pct": s.peak_pnl_pct, "held_seconds": held_s},
            ))
            self._reset_to_cooldown(s, ts_ms)
            return events

        if held_s >= self.cfg.max_position_seconds:
            events.append(EarlyRunnerEvent(
                EarlyRunnerEventType.EXIT_TIME_LIMIT, ts_ms, instrument,
                "⏰ SALIDA — LÍMITE DE TIEMPO ALCANZADO",
                f"{instrument}: la operación lleva {held_s/60:.0f} minutos. Resultado PAPER aproximado "
                f"{pnl_pct:+.2f}%. Se cierra la operación de esta estrategia corta.",
                s.state,
                {"pnl_pct": pnl_pct, "peak_pnl_pct": s.peak_pnl_pct, "held_seconds": held_s},
            ))
            self._reset_to_cooldown(s, ts_ms)
            return events

        still_strong = x["heat"] >= self.cfg.detector_heat_min and x["buy_ratio"] >= self.cfg.entry_buy_ratio_floor
        if still_strong and (
            s.last_hold_message_ms == 0
            or ts_ms - s.last_hold_message_ms >= int(self.cfg.hold_message_interval_seconds * 1000)
        ):
            s.last_hold_message_ms = ts_ms
            events.append(EarlyRunnerEvent(
                EarlyRunnerEventType.HOLD, ts_ms, instrument,
                "🟢 MANTENER — EL MOVIMIENTO SIGUE FUERTE",
                f"{instrument}: el impulso continúa activo. Resultado PAPER actual {pnl_pct:+.2f}% y máximo "
                f"alcanzado {s.peak_pnl_pct:+.2f}%. Se mantiene mientras no aparezcan señales de agotamiento.",
                s.state,
                {"pnl_pct": pnl_pct, "peak_pnl_pct": s.peak_pnl_pct, "held_seconds": held_s},
            ))

        return events
