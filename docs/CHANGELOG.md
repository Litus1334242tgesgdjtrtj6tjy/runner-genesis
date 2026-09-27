# Changelog

## v0.2.0-development — 2026-09-27

### Data correctness / state
- Added exact candidate universe gate and conservative asset identity handling.
- Added UNKNOWN semantics and removed fake calibrated-looking probabilities.
- Added Helius historical wallet backfill, conservative swap direction reconstruction, funding-link extraction and persisted research-state hydration.

### Smart Capital
- Added wallet-token positions, strategy classifier, conviction, accumulation, entry distance and weighted independent consensus.
- Added TRUE_SMART_CAPITAL_30D ranking and emerging-wallet scoring.
- Smart Capital confirmation now requires quality, strategy, conviction, accumulation and effective wallet breadth.

### Pump / clans / FOMO
- Added Pump/KOL discovery snapshots, rank dynamics and independent top-wallet waves.
- Added probabilistic cohort/clan detection using actor/funding evidence.
- Added optional FomoScan Pump leaderboard/callout adapter.
- Added bounded/cached background wallet research sync.

### Future-state research
- Added MiroFish-style local multi-agent scenario rollouts with candidate gating.
- Enabled FlyWire FAFB research reservoir with existing controls.
- Added reliability-aware Multi-Brain Fusion so correlated modules are not simply averaged.

### PAPER / risk
- Added PAPER-only untrained fusion research entries while retaining trained-model requirements outside PAPER.
- Added configurable T+60 delayed ENTER/ADD revalidation.
- Extended Risk Governor with manipulation, sellability, late-entry, fusion and wallet-cluster vetoes.
- Persisted paper pending/fill/invalidation updates.

### Evaluation / persistence
- Expanded DB research tables for wallet outcomes, funding relationships, paper updates, model versions, backtests and experiments.
- Added executable backtest metrics.
- Added deterministic component ablation harness and CLI command.
- Added GitHub CI for pytest, backtest smoke, ablation smoke and frontend production build.

### UI
- Added Smart Capital, Pump discovery, probabilistic clan, fusion, MiroFish/FlyWire and PAPER diagnostics to the existing dashboard.

### Verification
Latest verified code checkpoint before documentation refresh:
- 35 Python tests passed.
- frontend build passed.
- demo backtest and ablation smoke passed.
