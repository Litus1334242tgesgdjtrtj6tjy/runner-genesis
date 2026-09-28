from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .backtest import Backtester
from .config import Settings
from .orchestrator import RunnerGenesisOmega


@dataclass(frozen=True)
class AblationVariant:
    name: str
    flywire: bool
    mirofish: bool
    fomo: bool
    world_model: bool
    pump_discovery: bool


DEFAULT_ABLATIONS = (
    AblationVariant("CORE", False, False, False, False, False),
    AblationVariant("CORE_PLUS_WORLD", False, False, False, True, False),
    AblationVariant("CORE_PLUS_MIROFISH", False, True, False, False, False),
    AblationVariant("CORE_PLUS_WORLD_MIROFISH", False, True, False, True, False),
    AblationVariant("CORE_PLUS_FLYWIRE", True, False, False, False, False),
    AblationVariant("CORE_PLUS_PUMP_DISCOVERY", False, False, False, False, True),
    AblationVariant("CORE_PLUS_FOMO", False, False, True, False, False),
    AblationVariant("FULL", True, True, True, True, True),
)


def settings_for_variant(base: Settings, variant: AblationVariant) -> Settings:
    s = base.model_copy(deep=True)
    # Experiments must never activate real trading regardless of caller config.
    s.mode = "BACKTEST"
    s.live_trading = False
    s.features.setdefault("database_persistence", {})["enabled"] = False
    s.features.setdefault("flywire", {})["enabled"] = variant.flywire
    s.features.setdefault("world_model", {})["enabled"] = variant.world_model
    s.mirofish.enabled = variant.mirofish
    s.fomo.enabled = variant.fomo
    s.pump_discovery.enabled = variant.pump_discovery
    s.external_discovery.auto_refresh = False
    # External sources are never fetched during deterministic replay.
    s.external_discovery.fomoscan_enabled = False
    return s


class AblationRunner:
    """Deterministic same-dataset component ablation harness."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, path: str, variants=DEFAULT_ABLATIONS) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for variant in variants:
            cfg = settings_for_variant(self.settings, variant)
            engine = RunnerGenesisOmega(cfg)
            metrics = Backtester(engine).run(path, variant=variant.name)
            out[variant.name] = {
                "variant": asdict(variant),
                "metrics": asdict(metrics),
            }
        return out
