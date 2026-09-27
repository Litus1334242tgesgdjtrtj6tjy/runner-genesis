# Next Steps / Handoff

Read `MASTER_CONTEXT.md`, `CURRENT_STATE.md`, and this file first.

1. Verify branch `work/v0.2-smart-capital-world-model` and latest commit.
2. Run `python -m pytest -q`; expected current result is 17 passing tests.
3. Add a **real, point-in-time historical data/backfill adapter** for wallet transactions and resolved outcomes. Do not invent wallet PnL from incomplete current observations.
4. Add a configurable Pump leaderboard provider/scheduler only after verifying the current official/public source and its terms/shape. Store every observed snapshot with timestamp; never overwrite history.
5. Build executable-runner labels from historical price/liquidity + simulated execution costs and sellability.
6. Train/calibrate Genesis and future-state models chronologically and use expanding walk-forward evaluation.
7. Add benchmark/ablation runner for copytrade, top-PnL, unweighted consensus, weighted consensus, +accumulation, +entry distance, +independence, +Launch Integrity, +Market Acceleration, +Persistence, +FOMO, +World Model, +MiroFish, full system.
8. Only after evidence improves OOS executable metrics should any experimental brain be promoted.

Never enable live trading while continuing these steps.
