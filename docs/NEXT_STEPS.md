# Next Steps / Handoff

Read MASTER_CONTEXT.md, CURRENT_STATE.md and TEST_RESULTS.md first.

The core implementation is now far enough that the next meaningful step requires real point-in-time data rather than more speculative modules.

1. Keep LIVE_TRADING=false.
2. Put HELIUS_API_KEY in the local .env file. Never commit or paste the key into chat.
3. FOMOSCAN_API_KEY is optional but enables automatic Pump top-trader/callout discovery. Without it, Helius can still refresh wallets already stored or seeded in the registry.
4. Run scripts\CHECK_SETUP.bat.
5. Start scripts\RUN_PAPER.bat and then scripts\RUN_PARSED_SHADOW.bat.
6. Confirm /api/research/status, /api/smart-capital/wallets and /api/discovery/cohorts populate with real observations.
7. Accumulate enough PAPER/SHADOW history for future labels.
8. Build an executable-runner dataset:
   python -m runner_genesis.cli build-dataset --out data/training/executable_runner.csv
9. Evaluate chronologically:
   python -m runner_genesis.cli walk-forward data/training/executable_runner.csv
10. Only with adequate sample/class coverage, train a candidate model:
   python -m runner_genesis.cli train-genesis data/training/executable_runner.csv --out artifacts/models/genesis_model.joblib
11. Re-run component ablations on identical temporal data before promoting MiroFish, FlyWire or FOMO.

Current engineering follow-up:
- Completed PAPER fills, cash and open positions survive restart.
- A still-waiting delayed PAPER signal is not yet restored after an abrupt restart; this should be hardened before any long unattended PAPER session.

Continuation prompt:
"Continue RUNNER GENESIS Ω from branch work/v0.2-smart-capital-world-model. Read docs/MASTER_CONTEXT.md, docs/CURRENT_STATE.md and docs/NEXT_STEPS.md, verify the latest GitHub Actions run, and continue without enabling live trading."
