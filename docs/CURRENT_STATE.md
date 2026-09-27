# Current State

VERSION: 0.2.0-development
BRANCH: work/v0.2-smart-capital-world-model
LATEST VERIFIED CODE CHECKPOINT: 8751dd0b3555864fa73df646393258358995234d
SAFE_MODE_STATUS: PAPER / SHADOW / BACKTEST only. LIVE_TRADING=false. No private-key sender exists.

## Implemented
- Full runtime source and frontend are materialized as normal GitHub files.
- Exact-mint candidate gate, conservative BUY/SELL normalization and UNKNOWN-data semantics.
- Smart Capital wallet-token positions, strategy/style, conviction, accumulation, entry distance and persistence/distribution.
- Smart Capital confirmation now requires consensus + effective independent wallets + accumulation + conviction + wallet quality + strategy match.
- TRUE_SMART_CAPITAL_30D ranking and emerging-smart-wallet scoring.
- Pump/KOL discovery snapshots with rank velocity/acceleration and independent top-wallet wave features.
- Probabilistic wallet cohort/clan discovery from funding, transfers and synchronized activity. Cohorts are evidence clusters, never identity claims.
- Helius Enhanced Transactions wallet-history backfill with conservative ambiguous-swap rejection.
- Historical wallet outcome and funding evidence persistence; research state hydrates across process restarts.
- Optional FomoScan Pump leaderboard/callout adapter with bounded refresh/backfill concurrency and caching.
- Launch Integrity, manipulation/dump risk and sellability.
- World Model research layer.
- FlyWire FAFB reservoir and controls; enabled in PAPER config as an experimental feature only.
- MiroFish-style local future rollout engine; enabled in PAPER config but gated to meaningful candidates and labelled MODEL SIMULATION.
- Reliability-aware Multi-Brain Fusion. It groups correlated evidence instead of averaging every model and outputs a research score, not a calibrated probability.
- AI Paper Trader consumes fusion state. Untrained heuristic entries are permitted only in PAPER research; they remain prohibited outside PAPER when a trained model is required.
- Risk Governor remains final authority and vetoes sellability, manipulation, late entry and overly correlated wallet cohorts.
- ENTER/ADD is delayed by configurable T+60s and revalidated at the first verified market event at/after due time.
- PAPER signal/fill/invalidation updates are persisted.
- Expanded executable backtest metrics and deterministic component-ablation harness.
- Dashboard panels for candidates, fusion, MiroFish, top Pump discovery, TRUE smart wallets, probabilistic cohorts and open PAPER swings.
- GitHub CI runs Python tests, demo backtest, ablation smoke and frontend build.

## Verified
At the latest verified code checkpoint:
- Python: 35 passed.
- Frontend production build: success.
- Demo backtest: 35 events / 35 decisions / 0 fills / €300 ending equity.
- Ablation smoke: completed successfully.

Zero demo fills is not treated as an error: the bundled demo does not contain enough qualified independent Smart Capital evidence under the stricter confirmation gates.

## External data activation
Code is ready to use real research feeds, but credentials must remain local:
- HELIUS_API_KEY: activates historical wallet qualification/backfill.
- FOMOSCAN_API_KEY: optional automatic Pump leaderboard/callout discovery.
Do not commit either secret.

## Scientific status
IMPLEMENTED and TESTED does not mean VALIDATED EDGE.
Genesis remains UNTRAINED unless a trained artifact is supplied. MiroFish/FlyWire/FOMO are experimental context modules. No claim of profitable predictive edge is made until chronological walk-forward/OOS evaluation on real point-in-time data succeeds.
