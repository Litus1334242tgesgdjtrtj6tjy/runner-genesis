# Data Sources

## Helius / Solana
Helius is the primary read-only on-chain stream/history source when HELIUS_API_KEY is configured.

Implemented:
- parsed live event ingestion into the same PAPER engine;
- Enhanced Transactions wallet-history backfill;
- exact-mint swap reconstruction;
- conservative BUY/SELL classification;
- direct incoming SOL funding evidence with swap proceeds excluded;
- retry/backoff and bounded concurrent wallet backfill;
- organic qualification of wallets observed in live Pump/PumpSwap traffic.

Ambiguous token-token swaps are ignored instead of guessed.

## Pump discovery
Pump leaderboard/KOL observations are discovery context, not Smart Money truth. Historical snapshots are stored point-in-time and expire from current top-wallet context when stale. Every wallet must still earn weight from on-chain quality, strategy, conviction and independence.

## FomoScan
Optional external discovery adapter. The implementation uses the documented Pump trader leaderboard and Pump thesis/callout routes and authenticates with the configured API key. Provider timestamps are retained, and callouts are deduplicated before entering FOMO context.

Environment:
- FOMOSCAN_API_KEY
- FOMOSCAN_BASE_URL

Missing FomoScan credentials do not disable the on-chain core.

## Market data
DEX Screener enrichment is exact-mint only. Symbol fallback is forbidden. It supplies current verified price/liquidity/market-cap context and SOL/USD when available for PAPER fee conversion.

## Execution cost data
runner_genesis/fees.py contains a versioned Pump schedule identified as PUMP_FEES_2026-05-21:
- bonding curve total trading fee: 1.25%;
- canonical PumpSwap SOL/USDC tiers: market-cap dependent;
- noncanonical PumpSwap total trading fee: 0.30%;
- insufficient tier/canonical detail uses a conservative Pump fallback rather than a cheaper guessed fee.

Solana network fee inputs are separately configurable. The PAPER engine can charge network cost on failed simulated transactions when SOL/USD is available.

These cost schedules are research inputs and must be re-verified when provider/protocol fee rules change.

## FOMO / social
FOMO is context only: discovery, confirmation, persistence and divergence. It is not an unconditional BUY trigger.

## MiroFish
Current MiroFish is a local role/scenario rollout engine. It consumes Smart Capital, independent wallet breadth, top-wallet independence and coordinated-clan risk. Outputs are simulation frequencies/proxies, not calibrated probabilities.

## FlyWire
Real preprocessed FlyWire/FAFB artifacts live under artifacts/flywire together with shuffled, rewired, degree-preserved and random-reservoir controls. FlyWire state is isolated per token and remains experimental until OOS ablation proves incremental value.
