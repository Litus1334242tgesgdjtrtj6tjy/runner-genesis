# Current State

VERSION: v0.2.0-work
BRANCH: work/v0.2-smart-capital-world-model
SAFE_MODE_STATUS: PAPER ONLY / LIVE_TRADING=false

## Completed in the current implementation pass
- Full v0.1.2 ZIP source recovered and audited locally.
- Existing baseline tests preserved and suite expanded to 19 passing tests.
- Smart Capital wallet-token position reconstruction.
- Wallet strategy classifier: SCALPER/RUNNER/SWING/HOLDER/MIXED/UNKNOWN.
- Accumulation, conviction, weighted consensus and effective-wallet breadth.
- Actor-graph independence correction.
- Entry-distance and ENTRY_TOO_LATE semantics.
- Launch Integrity / coordinated dump / sellability research features.
- Optional FOMO context engine with safe disabled fallback.
- Optional MiroFish Future Rollout Engine with deterministic seeded simulations.
- Pump leaderboard point-in-time snapshot engine (provider-fed; no invented external endpoint).
- Expanded SQLAlchemy research tables for wallet metrics, leaderboard snapshots, wallet positions, smart token states, transitions and rollout summaries.
- Untrained Genesis no longer emits fake-looking X2/X5 probabilities.
- World heuristic outputs explicitly marked UNTRAINED_SIMULATION.
- New features integrated into orchestrator, trader, Risk Governor, API and dashboard locally.
- Local pytest result: 19 passed.
- Demo backtest completed: 35 events / 35 decisions / no crashes.

## Repository note
The GitHub branch existed with bootstrap payload chunks but still did not expose the full runtime source tree directly. The authoritative full v0.2 working tree currently exists in the generated local package/ZIP from this ChatGPT session. Do not invent missing source from egg-info.

## Pending
- Real Pump.fun official leaderboard adapter and durable snapshot ingestion.
- Historical 500–1000 wallet backfill and queue/cache layer.
- Full PnL reconstruction across all swaps/transfers/funding paths.
- Real KOL/FOMO providers.
- Walk-forward/OOS model promotion.
- Event-scheduled T+delay paper execution.
- MiroFish ablation vs simple stochastic controls.
