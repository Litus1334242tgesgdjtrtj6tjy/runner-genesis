# Implementation Plan

## Completed foundation
1. Repository audit and source restoration.
2. Data-correctness/candidate gate.
3. Smart Capital data structures and state.
4. Pump/KOL discovery registry and historical snapshots.
5. Position reconstruction.
6. Wallet quality/style/conviction/accumulation.
7. Actor/Funding independence and effective wallet count.
8. Weighted consensus and entry distance.
9. Launch Integrity.
10. Persistence/distribution integration.
11. Optional FOMO context.
12. Optional MiroFish-style rollout engine.
13. Delayed realistic PAPER entry and Risk Governor integration.
14. Dashboard/API expansion and tests.

## Next implementation/research phases
1. Real historical wallet backfill adapters and incremental cache layer.
2. Verified Pump official/top-trader source adapter with snapshot scheduler.
3. Historical token outcome labelling based on **executable** return, not chart peak.
4. Walk-forward datasets and model training/calibration.
5. Benchmark/ablation runner A→N.
6. Route-specific DEX/protocol fee schedules with effective-date versioning.
7. Async deep-path workers for rollouts/backfills and scale tests at 500–1000 wallets.
8. Dashboard drill-down charts built only from verified observations.
