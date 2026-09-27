# RUNNER GENESIS Ω — v0.2.0-development

PAPER-only, on-chain-first research system for detecting early Solana memecoin runner formation, reconstructing smart-capital behavior and testing whether signals survive realistic execution costs.

**Safety:** `LIVE_TRADING=false` by default. This repository contains no private-key handling and no live order sender.

## v0.2 highlights
- Candidate Universe Gate with exact-mint identity.
- Smart Capital wallet/token position reconstruction.
- wallet quality/style, conviction and accumulation.
- Actor/Funding independence and `EFFECTIVE_WALLET_COUNT` for Pump-style cohorts/clans.
- Pump official/top-trader/KOL discovery registry with historical snapshots.
- weighted smart-capital consensus and entry-distance validation.
- Launch Integrity, coordinated-dump risk and sellability.
- optional FOMO/attention context.
- optional local **MiroFish-style Future Rollout Engine** (disabled by default).
- Runner Persistence/Distribution extensions.
- delayed PAPER ENTER/ADD execution using post-delay market observations.
- untrained model outputs display as UNTRAINED rather than fake probabilities.
- expanded FastAPI endpoints, dashboard, SQLAlchemy research persistence and tests.

## Windows install

```bat
scripts\INSTALL_WINDOWS.bat
```

Then run the single PAPER API/engine:

```bat
scripts\RUN_PAPER.bat
```

Dashboard in another terminal:

```bat
scripts\RUN_DASHBOARD.bat
```

For real on-chain SHADOW ingestion into the same PAPER engine:

```bat
scripts\RUN_PARSED_SHADOW.bat
```

Put `HELIUS_API_KEY` in local `.env`. **Never commit `.env`.**

## Research defaults
Genesis and World Model are untrained unless model artifacts exist. `trader.require_trained_for_entry: true` means the default system can WATCH but will not open a new PAPER position from an untrained Genesis score. MiroFish and FOMO are OFF by default.

## Key APIs
- `POST /api/event`
- `POST /api/helius/webhook`
- `GET /api/tokens`
- `GET /api/token/{mint}`
- `GET /api/smart-capital/wallets`
- `GET /api/smart-capital/tokens`
- `GET /api/paper/swings`
- `POST/GET /api/discovery/pump/leaderboard`
- `POST /api/discovery/wallet`
- `POST /api/discovery/fomo`
- `GET /api/discovery/fomo/{mint}`
- `GET /api/state-transitions`
- `GET /api/alerts`

## Tests

```bat
scripts\TEST.bat
```

Current local implementation pass: 17 tests passing plus compile/API smoke checks. See `docs/TEST_RESULTS.md`.

## Project memory
For continuation in another ChatGPT/Work session, read:
1. `docs/MASTER_CONTEXT.md`
2. `docs/CURRENT_STATE.md`
3. `docs/NEXT_STEPS.md`

GitHub is the canonical persistent project memory.
