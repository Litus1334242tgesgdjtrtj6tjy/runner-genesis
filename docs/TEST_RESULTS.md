# Test Results

Latest local command:

```text
python -m pytest -q
```

Result: **17 passed**.

Additional checks:
- `python -m compileall -q runner_genesis` succeeded.
- FastAPI TestClient `/health`, `/api/tokens`, `/api/smart-capital/wallets` returned HTTP 200.
- Demo end-to-end backtest processed 35 events and 35 decisions without a live trade path.

Coverage includes existing point-in-time/asset gate/capital surprise/risk/execution/FlyWire/replay/shadow tests plus new Smart Capital position, transfer!=sell, same-funder independence, weighted consensus, entry distance, Launch Integrity, FOMO point-in-time filtering, untrained-probability behavior, deterministic MiroFish rollouts and delayed PAPER entry.
