from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_doctor_report(settings) -> dict[str, Any]:
    fly_cfg = settings.features.get("flywire", {})
    fly_dir = Path(fly_cfg.get("artifact_dir", "./artifacts/flywire"))
    fly_files = {
        "real": fly_dir / "adjacency.npz",
        "shuffled": fly_dir / "fly_shuffled_weights.npz",
        "rewired": fly_dir / "fly_rewired.npz",
        "degree_preserved": fly_dir / "fly_degree_preserved.npz",
        "random": fly_dir / "random_reservoir.npz",
        "metadata": fly_dir / "metadata.json",
    }
    genesis_path = Path(settings.features.get("genesis_model", {}).get("model_path", "./artifacts/models/genesis_model.joblib"))
    world_path = Path(settings.features.get("world_model", {}).get("model_path", "./artifacts/models/world_model.joblib"))

    checks = {
        "live_trading_off": not bool(settings.live_trading),
        "paper_safe_mode": bool(settings.paper_only),
        "helius_key_present": bool(settings.helius_api_key),
        "fomoscan_key_present": bool(settings.fomoscan_api_key),
        "flywire_real_present": fly_files["real"].exists(),
        "flywire_controls_complete": all(fly_files[k].exists() for k in ("shuffled", "rewired", "degree_preserved", "random")),
        "flywire_metadata_present": fly_files["metadata"].exists(),
        "genesis_model_trained_artifact_present": genesis_path.exists(),
        "world_model_trained_artifact_present": world_path.exists(),
    }

    blockers = []
    if not checks["live_trading_off"]:
        blockers.append("LIVE_TRADING_MUST_REMAIN_FALSE")
    if not checks["helius_key_present"]:
        blockers.append("HELIUS_API_KEY_REQUIRED_FOR_REAL_ONCHAIN_HISTORY_AND_SHADOW")
    if not checks["fomoscan_key_present"]:
        blockers.append("FOMOSCAN_API_KEY_OPTIONAL_FOR_AUTOMATIC_PUMP_LEADERBOARD_AND_CALLOUT_DISCOVERY")
    if bool(fly_cfg.get("enabled", False)) and not checks["flywire_real_present"]:
        blockers.append("FLYWIRE_ENABLED_BUT_ARTIFACT_MISSING")

    research_ready = (
        checks["live_trading_off"]
        and checks["paper_safe_mode"]
        and checks["helius_key_present"]
    )
    automatic_pump_discovery_ready = research_ready and checks["fomoscan_key_present"]
    return {
        "mode": settings.mode,
        "live_trading": settings.live_trading,
        "research_ready": research_ready,
        "automatic_pump_discovery_ready": automatic_pump_discovery_ready,
        "checks": checks,
        "blockers_or_optional_missing": blockers,
        "notes": {
            "genesis": "TRAINED_ARTIFACT_PRESENT" if checks["genesis_model_trained_artifact_present"] else "UNTRAINED_RESEARCH_SCORE_ONLY",
            "world_model": "TRAINED_ARTIFACT_PRESENT" if checks["world_model_trained_artifact_present"] else "UNTRAINED_RESEARCH_SCORES",
            "mirofish": "LOCAL_MODEL_SIMULATION" if settings.mirofish.enabled else "DISABLED",
            "flywire": "EXPERIMENTAL_RESERVOIR" if bool(fly_cfg.get("enabled", False)) else "DISABLED",
            "fomo": "CONTEXT_ONLY" if settings.fomo.enabled else "DISABLED",
        },
    }


def doctor_json(settings) -> str:
    return json.dumps(build_doctor_report(settings), indent=2, default=str)
