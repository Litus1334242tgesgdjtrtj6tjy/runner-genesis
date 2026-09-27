# Architecture

## Existing/reused modules
The v0.2 work reuses the existing Event store, Capital Surprise, Wallet Quality, Actor Graph, Funding Graph, Market Acceleration, Token Quality, Hawkes, Graph Flow, Temporal Hypergraph, Sequence, Jump-SDE, Elite Holder, quantum-inspired graph, FlyWire reservoir, Genesis, World Model, Persistence, Executable Alpha, AI Paper Trader, Risk Governor, Paper Execution, Portfolio, FastAPI API and React/Vite dashboard.

## New v0.2 modules
- `runner_genesis/ingestion/gates.py` — exact-mint Candidate Universe Gate.
- `runner_genesis/providers.py` — provider interfaces for future external adapters.
- `runner_genesis/engines/discovery.py` — point-in-time Pump/KOL/community discovery registry and leaderboard snapshots.
- `runner_genesis/engines/smart_capital.py` — wallet-token positions, style, conviction, accumulation, weighted consensus, entry distance and smart-capital state transitions.
- `runner_genesis/engines/launch_integrity.py` — manipulation/dump/sellability research scores.
- `runner_genesis/engines/fomo.py` — optional external attention/FOMO observations.
- `runner_genesis/engines/mirofish.py` — optional deterministic-seeded multi-agent rollout simulator.
- `runner_genesis/alerts.py` — deduplicated in-process PAPER/SHADOW alerts.

## Fast vs deep path
The current implementation runs synchronously inside the reference process. MiroFish and FOMO are disabled by default. A later scale phase should move expensive enrichment/backfills/rollouts behind bounded async queues so real-time ingestion cannot be blocked.

## Persistence
SQLAlchemy keeps append-only research tables for events, decisions, fills, wallet metrics/positions, leaderboard snapshots, smart-token states, state transitions, discovery observations, actor-cluster snapshots and rollout summaries. v0.2 uses additive `create_all` at runtime; `migrations/0001_smart_capital.sql` documents the additive schema.
