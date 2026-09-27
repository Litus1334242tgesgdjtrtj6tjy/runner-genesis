# RUNNER GENESIS Ω

## v0.1.1 Windows portability fix

Fixed the test suite so it resolves the repository root dynamically instead of using the build-environment path `/mnt/data/runner_genesis_omega`. This affects tests only; runtime paper/shadow code was not using that path.

Paper-only, on-chain-first research system for testing whether early Solana memecoin runner formation can be detected and managed with executable edge.

**Important:** `LIVE_TRADING=false` by default. There is no private-key handling and no live order sender in this version.

## What runs today

The repository supports normalized event ingestion, replay/backtest, a paper portfolio, a hard Risk Governor, realistic execution simulation, a FastAPI backend, a React dashboard, model-training hooks, and optional research engines including a real sparse FlyWire/FAFB v783 reservoir.

The default Genesis and World Model behavior is an explicitly untrained conservative baseline until you provide a point-in-time historical market dataset and run training/walk-forward validation. The software does not label an untrained score as scientifically calibrated probability.

## Windows install

1. Put the project in a normal local folder.
2. Open `scripts\INSTALL_WINDOWS.bat`.
3. It creates `.venv`, installs dependencies, creates demo replay data, and runs the test suite.

Run the API/paper engine:

```bat
scripts\RUN_PAPER.bat
```

Run the dashboard in another terminal:

```bat
scripts\RUN_DASHBOARD.bat
```

Open the Vite URL shown in that terminal (normally `http://localhost:5173`).

To feed **real Solana data into the same PAPER engine/dashboard**, keep `RUN_PAPER.bat` running and open a third terminal:

```bat
scripts\RUN_PARSED_SHADOW.bat
```

`RUN_PARSED_SHADOW.bat` reads `HELIUS_API_KEY` from the project `.env`, normalizes/enriches incoming events, and POSTs them into the API-owned PAPER engine. This guarantees the dashboard, Risk Governor and paper portfolio share one state.

## Backtest / replay

```bat
scripts\RUN_BACKTEST.bat data\demo\demo_events.jsonl
scripts\RUN_REPLAY.bat data\demo\demo_events.jsonl
```

Normalized replay events are JSONL or CSV representations of `MarketEvent` in `runner_genesis/domain/events.py`.

## Helius / Solana ingestion

Two routes are included:

- `POST /api/helius/webhook` for decoded webhook payloads.
- low-level standard Solana `logsSubscribe` helper for custom decoders.

The code also includes a `HeliusParsedEventNormalizer` for Helius Parsed Events/Parsed Streams swap summaries that explicitly carry `input_mint` and `output_mint`. It refuses to infer assets by token symbol.

For production shadow ingestion, use a paid/available Helius Parsed Stream or webhook and configure protocol/program filters appropriate to your account. Program-specific decoding is deliberately isolated from the feature engine so protocol upgrades do not corrupt historical model logic.

## FlyWire preprocessing

Use the filtered Princeton connectivity file first:

```bat
scripts\PREPROCESS_FLYWIRE.bat D:\data\connections_princeton.csv.gz
```

Default output is `artifacts\flywire\adjacency.npz`, `root_ids.npy`, and `metadata.json`.

The default production preprocessing selects a 20k-node top weighted-degree induced subgraph with `syn_count >= 2`. This is a compute choice, not a scientific claim. Full research runs may increase or remove `max_nodes` after RAM profiling.

The FlyWire engine uses the actual sparse weighted connectivity matrix. It never interprets numeric root IDs as semantic features.

## Models

`runner_genesis/ml/train.py` expects a point-in-time feature table with chronological `decision_time`, the feature columns in `FEATURE_ORDER`, and labels such as `genesis_label`, `x2_60m`, `x5_60m`, `x10_60m`.

It performs a chronological 70/15/15 train/validation/test split and calibration on the validation slice when possible. For serious research, replace the simple split with the included expanding walk-forward utility and log every experiment/dataset/model version.

## Core safety / correctness rules

- mint address is the asset identity;
- future information must never enter historical wallet, actor, cluster, analogue or model features;
- no random split as primary evaluation;
- paper execution uses costs, impact, latency, failures and partial fills;
- AI Trader proposals are subordinate to Risk Governor;
- advanced engines are hypotheses, not presumed edge;
- post-trade reviews can propose experiments but cannot mutate production automatically.

## Tests

```bat
scripts\TEST.bat
```

Current tests cover point-in-time exclusion, future-leakage guard, Capital Surprise history behavior, asset-match gating, risk veto, deterministic execution, FlyWire sparse preprocessing and end-to-end replay.

## Repository map

- `runner_genesis/domain/` — events/state
- `runner_genesis/ingestion/` — replay, Solana/Helius adapters
- `runner_genesis/engines/` — signal/state engines
- `runner_genesis/flywire/` — FAFB preprocessing
- `runner_genesis/ml/` — training
- `runner_genesis/evaluation/` — walk-forward helpers
- `runner_genesis/api/` — FastAPI
- `frontend/` — React/Vite dashboard
- `tests/` — correctness tests
- `config/default.yaml` — feature/risk/execution/trader config
- `scripts/` — Windows launchers
- `audit/PROJECT_AND_FLYWIRE_AUDIT.md` — Phase 0/1 audit
