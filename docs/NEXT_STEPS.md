# Next Steps

1. Materialize the full v0.2 runtime source tree into GitHub (the branch currently contains bootstrap chunks rather than all source files as browseable files).
2. Wire SQLAlchemy persistence into the live orchestrator for wallet metrics, leaderboard snapshots, positions, smart token states and transitions.
3. Implement a real PumpLeaderboardProvider using documented/verified data only; preserve historical point-in-time snapshots.
4. Add Helius transaction-history backfill for wallet PnL reconstruction and funding/internal-transfer classification.
5. Add configurable Pump/KOL/cohort discovery adapters; verify every wallet on-chain before weighting.
6. Implement event-scheduled paper entry at T0 + execution_delay_seconds.
7. Build walk-forward benchmarks A–N and store experiment metadata.
8. Compare CORE vs simple stochastic rollout vs World Model vs MiroFish before promotion.
9. Keep LIVE_TRADING=false.
