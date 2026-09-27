# Changelog

## v0.2.0-development — 2026-09-27

### Data correctness / state
- Added exact candidate universe gate and conservative asset identity handling.
- Added UNKNOWN semantics and removed fake calibrated-looking probabilities.
- Added Helius historical wallet backfill, conservative swap direction reconstruction, funding-link extraction and persisted research-state hydration.
- Added event idempotency, restart hydration and right-censor protection for future labels.
- Added bounded/shared exact-mint market enrichment.

### Smart Capital
- Added wallet-token positions, strategy classifier, conviction, accumulation, entry distance and weighted independent consensus.
- Added TRUE_SMART_CAPITAL_30D ranking and Emerging Smart Wallet scoring.
- Smart Capital confirmation requires quality, strategy, conviction, accumulation and effective wallet breadth.
- Added wallet research priority scoring for scarce Helius budget.
- Added stale/future-rank protection to research priority.
- Added Early Smart Capital Formation as an experimental lead-time challenger.

### Pump / clans / FOMO
- Added Pump/KOL discovery snapshots, rank dynamics and independent top-wallet waves.
- Added probabilistic cohort/clan detection using actor/funding evidence.
- Added weighted community splitting for bridged wallet populations.
- Separated clan alpha quality from coordination risk so dense same-funder clusters are not automatically treated as superior alpha.
- Added optional FomoScan Pump leaderboard/callout adapter.
- Added bounded/cached background wallet research sync and on-chain fallback when external discovery is unavailable.

### Future-state research
- Added MiroFish-style local scenario rollouts with candidate gating.
- Added stable-state MiroFish caching for PAPER/SHADOW efficiency.
- BACKTEST/REPLAY MiroFish now executes exact deterministic rollout counts rather than depending on wall-clock timeout.
- MiroFish now consumes independent-wallet breadth, clan coordination risk and Early Formation context.
- Enabled FlyWire FAFB research reservoir with controls and isolated recurrent state per token.
- Added reliability-aware Multi-Brain Fusion so correlated modules are not simply averaged.

### PAPER / risk
- Added PAPER-only untrained fusion research entries while retaining trained-model requirements outside PAPER.
- Added configurable T+60 delayed ENTER/ADD revalidation.
- Extended Risk Governor with manipulation, sellability, late-entry, fusion and wallet-cluster vetoes.
- Added current Pump protocol-fee tier simulation and Solana network-fee accounting, including failed simulated transactions.
- Persisted PAPER pending/fill/invalidation state and recovery across restarts.

### Evaluation
- Added executable-runner labels with full-horizon/right-censor checks.
- Added label-availability purge to chronological train/validation/test and walk-forward splits.
- Added precision, recall, F1, precision@top-decile, PR-AUC, ROC-AUC, Brier, log-loss and calibration error.
- Expanded executable trade metrics with net PnL, ROI, expectancy, profit factor, drawdown, hold time, MFE/MAE, captured MFE, multibagger rates, turnover and costs.
- Added deterministic component-ablation harness and CLI commands.

### Performance / scale
- Added bounded concurrency, retry/backoff, cache reuse and provider fallback.
- Added service-funder hub downweighting and 1000-wallet sparse-graph safeguards.
- Added MiroFish deep-path rerun controls to avoid repeated near-identical simulations during event bursts.

### UI
- Added Smart Capital, Pump discovery, wallet priority context, probabilistic clan alpha/risk, Early Formation, fusion, MiroFish/FlyWire and PAPER diagnostics to the dashboard.

### Verification
Latest verified checkpoint:
- commit be386666df00621902918aed9c818d5c5cd7897d
- GitHub Actions run 264
- 108 Python tests passed
- frontend production build passed
- demo backtest and component-ablation smoke passed
