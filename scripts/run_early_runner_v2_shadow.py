from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml

from runner_genesis.engines.early_runner_v2 import EarlyRunnerConfig, EarlyRunnerV2Engine
from runner_genesis.telegram_notifier import TelegramNotifier


def load_cfg(path: str | None) -> EarlyRunnerConfig:
    if not path:
        return EarlyRunnerConfig()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return EarlyRunnerConfig.from_mapping(raw)


def main() -> int:
    ap = argparse.ArgumentParser(description="Live tail of Flight Recorder for EARLY_RUNNER_V2 SHADOW/PAPER.")
    ap.add_argument("flight_dir", help="Directory containing flight_*.jsonl files")
    ap.add_argument("--config", default="config/early_runner_v2_shadow.yaml")
    ap.add_argument("--poll-seconds", type=float, default=0.5)
    ap.add_argument("--telegram", action="store_true", help="Send Spanish events to Telegram using env credentials")
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    engine = EarlyRunnerV2Engine(cfg)
    notifier = TelegramNotifier.from_env() if args.telegram else None
    if args.telegram and notifier is None:
        raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID")

    root = Path(args.flight_dir)
    offsets: dict[Path, int] = {}
    print(json.dumps({"status": "EARLY_RUNNER_V2_SHADOW_STARTED", "flight_dir": str(root), "telegram": bool(notifier)}, ensure_ascii=False), flush=True)

    while True:
        files = sorted(root.glob("flight_*.jsonl*"))
        for path in files:
            offset = offsets.get(path, 0)
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                continue
            if size < offset:
                offset = 0
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                while True:
                    pos = fh.tell()
                    line = fh.readline()
                    if not line:
                        fh.seek(pos)
                        break
                    if not line.endswith("\n"):
                        fh.seek(pos)
                        break
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("type") != "RADAR_SAMPLE":
                        continue
                    for event in engine.process(row):
                        payload = event.as_dict()
                        payload["telegram_text"] = event.telegram_text
                        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
                        if notifier is not None:
                            notifier.send(event)
                offsets[path] = fh.tell()
        time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
