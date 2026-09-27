# Data Sources

## Helius / Solana
Helius is the primary read-only research/backfill source when HELIUS_API_KEY is configured.

Implemented:
- live/parsed event ingestion already present in the project;
- Enhanced Transactions address-history backfill;
- exact-mint wallet swap reconstruction;
- conservative BUY/SELL classification;
- incoming SOL funding evidence;
- retry/backoff and bounded concurrent top-wallet backfill.

Ambiguous token-token swaps are ignored instead of guessed.

Environment:
- HELIUS_API_KEY
- HELIUS_WEBHOOK_SECRET
- SOLANA_RPC_HTTP
- SOLANA_RPC_WS
- RUNNER_API_URL

## Pump discovery
The system maintains point-in-time Pump/KOL discovery snapshots. Discovery status never equals Smart Money automatically: every wallet must earn weight from on-chain quality, strategy, conviction and independence.

The API also accepts explicit Pump leaderboard snapshots for research ingestion.

## FomoScan
Optional external discovery adapter:
- Pump trader leaderboard
- Pump callout/thesis observations used as FOMO/discovery context

Environment:
- FOMOSCAN_API_KEY
- FOMOSCAN_BASE_URL

The adapter is optional. Missing credentials must not crash the on-chain core.

## FOMO / social
FOMO is context only: discovery, confirmation, persistence and divergence. It is never an unconditional BUY trigger.

## Market data
Any external price/market-cap enrichment must verify exact mint identity. Symbol fallback is forbidden.

## MiroFish
Current MiroFish implementation is a local MiroFish-style role/scenario rollout engine, not an external MiroFish service. Outputs are explicitly simulation frequencies/proxies, not calibrated probabilities or claims of foresight.

## FlyWire
The project uses the real preprocessed FlyWire/FAFB artifacts already stored under artifacts/flywire plus shuffled/rewired/degree-preserved/random controls. It remains experimental until OOS ablation proves incremental value.
