# Next Steps / Handoff

Read MASTER_CONTEXT.md, CURRENT_STATE.md and TEST_RESULTS.md first.

The main bottleneck is now real point-in-time data and validation rather than missing core architecture.

1. Keep LIVE_TRADING=false.
2. Put HELIUS_API_KEY in local .env. Never commit or paste the key into chat.
3. Run scripts\CHECK_SETUP.bat.
4. Start scripts\RUN_PAPER.bat and then scripts\RUN_PARSED_SHADOW.bat.
5. Optionally add FOMOSCAN_API_KEY for automatic Pump leaderboard/callout discovery. Without it, live on-chain wallets are still queued for Helius qualification and Emerging Smart Wallet scoring.
6. Confirm /api/research/status, /api/smart-capital/wallets, /api/discovery/cohorts and the dashboard populate with real observations.
7. Leave PAPER running long enough to collect point-in-time decisions plus future executable outcomes.
8. Build the executable-runner dataset:
   python -m runner_genesis.cli build-dataset --out data/training/executable_runner.csv
9. Run chronological walk-forward:
   python -m runner_genesis.cli walk-forward data/training/executable_runner.csv
10. Only when sample/class coverage is adequate, train a candidate Genesis artifact:
    python -m runner_genesis.cli train-genesis data/training/executable_runner.csv --out artifacts/models/genesis_model.joblib
11. Run component ablations on identical temporal data before promoting MiroFish, FlyWire or FOMO.
12. After enough real load exists, benchmark 500-1000 actively tracked wallets and tune provider quotas/caches from observed limits rather than guesses.

No additional AI module should be promoted simply because it exists. Promotion remains IMPLEMENTED -> TESTED -> OOS VALIDATED -> SHADOW VALIDATED -> PAPER PROMOTED.

Continuation prompt:
"Continue RUNNER GENESIS Ω from branch work/v0.2-smart-capital-world-model. Read docs/MASTER_CONTEXT.md, docs/CURRENT_STATE.md and docs/NEXT_STEPS.md, verify the latest GitHub Actions run, and continue without enabling live trading."
