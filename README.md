# RUNNER GENESIS Ω — v0.3.0

PAPER/SHADOW/BACKTEST research system for detecting early Solana memecoin runner formation, reconstructing Smart Capital behavior and testing signals against realistic execution frictions. The default dashboard is now a portfolio-style PAPER profile rather than an engineering console.

**Safety:** `LIVE_TRADING=false` by default. The repository contains no private-key handling and no live order sender. The event/config models are locked to the **Solana** network.

## Current flow

Solana/Pump events -> exact-mint gate -> wallet quality + Actor/Funding Graph -> Pump top-wallet / Emerging Smart Wallet / wallet-priority research -> Smart Capital -> probabilistic clan alpha/risk -> Early Formation -> Launch Integrity + Market/Hawkes/Flow -> World Model -> FlyWire + MiroFish -> Multi-Brain Fusion -> AI Paper Trader -> Risk Governor -> delayed PAPER execution -> persistence/review.

MiroFish, FlyWire, FOMO and Early Formation are experimental research components. None is treated as validated alpha and none bypasses the Risk Governor.

## Key capabilities
- exact mint identity and conservative UNKNOWN semantics;
- Smart Capital wallet/token position reconstruction;
- wallet quality/style, conviction, accumulation and independent weighted consensus;
- TRUE_SMART_CAPITAL_30D and Emerging Smart Wallet discovery;
- point-in-time Pump top-wallet snapshots with stale-rank expiry;
- wallet research priority for scarce Helius budget;
- probabilistic wallet clans/cohorts with shared-funder hub correction, community splitting and separate alpha/risk scores;
- Helius-only organic wallet qualification when no external Pump leaderboard provider is configured;
- Launch Integrity / coordinated-dump / sellability research features;
- experimental Early Smart Capital Formation for earlier setup detection before excessive price extension;
- local MiroFish-style future rollouts with PAPER/SHADOW caching and deterministic full-rollout BACKTEST/REPLAY behavior;
- real FlyWire/FAFB reservoir controls with per-token recurrent state;
- reliability-aware Multi-Brain Fusion;
- delayed PAPER ENTER/ADD at T+60 with revalidation;
- Pump protocol fee tiers, Solana network fee accounting, slippage/impact, failures and partial fills;
- persistent PAPER positions/pending signals/research state across restarts;
- executable-runner labels with right-censor protection;
- chronological training, label-availability purge, walk-forward evaluation and component ablations;
- Pump/FOMO-style PAPER account profile with €300 starting balance, equity curve, daily/weekly/monthly/total PnL, realized/unrealized PnL, open positions, closed cycles, fees, win rate and execution history;
- token name/symbol/profile-image enrichment from exact-mint Solana market metadata, persisted across restarts with deterministic avatar fallback;
- advanced Radar/System tabs preserve candidate, fusion, Smart Capital, MiroFish/FlyWire and runtime diagnostics.

## Windows

Install:
```bat
scripts\INSTALL_WINDOWS.bat
```

Check local readiness:
```bat
scripts\CHECK_SETUP.bat
```

Start the single PAPER API/engine:
```bat
scripts\RUN_PAPER.bat
```

Dashboard in another terminal:
```bat
scripts\RUN_DASHBOARD.bat
```

Real on-chain SHADOW ingestion into the same PAPER engine:
```bat
scripts\RUN_PARSED_SHADOW.bat
```

Put `HELIUS_API_KEY` in local `.env`. Never commit `.env`. `FOMOSCAN_API_KEY` is optional for automatic Pump leaderboard/callout discovery.

## Training / validation

After enough real PAPER/SHADOW history exists:
```bat
python -m runner_genesis.cli build-dataset --out data/training/executable_runner.csv
python -m runner_genesis.cli walk-forward data/training/executable_runner.csv
python -m runner_genesis.cli train-genesis data/training/executable_runner.csv --out artifacts/models/genesis_model.joblib
```

Do not interpret an untrained research score as a calibrated probability. Experimental modules are promoted only after chronological OOS/shadow/PAPER evidence.

## Tests

Current v0.3 profile checkpoint:
- 156 Python tests passed;
- demo backtest smoke passed;
- component ablation smoke passed;
- frontend production build passed.

## Project memory

For continuation from another ChatGPT/Work session, read:
1. `docs/MASTER_CONTEXT.md`
2. `docs/CURRENT_STATE.md`
3. `docs/NEXT_STEPS.md`

GitHub is the canonical persistent project memory.
