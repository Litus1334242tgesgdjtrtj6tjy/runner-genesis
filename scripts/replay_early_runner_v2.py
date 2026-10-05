from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import yaml

from runner_genesis.engines.early_runner_v2 import EarlyRunnerConfig, EarlyRunnerV2Engine


def iter_paths(values: list[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for raw in values:
        p = Path(raw)
        candidates = sorted(p.glob("*.jsonl*")) if p.is_dir() else [p]
        for item in candidates:
            item = item.resolve()
            if item not in seen and item.is_file():
                seen.add(item)
                yield item


def load_cfg(path: str | None) -> EarlyRunnerConfig:
    if not path:
        return EarlyRunnerConfig()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return EarlyRunnerConfig.from_mapping(raw)


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay Flight Recorder JSONL through EARLY_RUNNER_V2 (SHADOW/PAPER only).")
    ap.add_argument("inputs", nargs="+", help="JSONL files or directories")
    ap.add_argument("--config", default=None, help="Optional YAML config")
    ap.add_argument("--events-out", default="early_runner_v2_events.jsonl")
    args = ap.parse_args()

    engine = EarlyRunnerV2Engine(load_cfg(args.config))
    out_path = Path(args.events_out)
    totals: dict[str, int] = {}
    malformed = 0
    samples = 0

    with out_path.open("w", encoding="utf-8") as out:
        for path in iter_paths(args.inputs):
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        malformed += 1
                        continue
                    if row.get("type") != "RADAR_SAMPLE":
                        continue
                    samples += 1
                    for event in engine.process(row):
                        payload = event.as_dict()
                        payload["telegram_text"] = event.telegram_text
                        out.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
                        totals[event.event_type.value] = totals.get(event.event_type.value, 0) + 1

    print(json.dumps({
        "mode": "SHADOW/PAPER",
        "samples": samples,
        "malformed_lines": malformed,
        "events": totals,
        "events_out": str(out_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
