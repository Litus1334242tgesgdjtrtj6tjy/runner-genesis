# Current State

VERSION: 0.2.0-development
BRANCH: work/v0.2-smart-capital-world-model
LATEST VERIFIED CODE CHECKPOINT: cf1cdc51e83922a057350bac65703fda6cb6572f
SAFE_MODE_STATUS: PAPER / SHADOW / BACKTEST only. LIVE_TRADING=false. No private-key sender exists.

## Implemented
- Exact-mint candidate gate, conservative BUY/SELL normalization and UNKNOWN-data semantics.
- Smart Capital wallet-token positions, strategy/style, conviction, accumulation, entry distance, persistence/distribution and restart hydration.
- TRUE_SMART_CAPITAL_30D and Emerging Smart Wallet scoring from resolved point-in-time history.
- Pump/KOL discovery snapshots with as-of rank dynamics, stale-snapshot expiry and independent top-wallet wave features.
- Helius-only organic qualification of wallets observed in live Pump/PumpSwap traffic; these are candidates, not automatically top wallets.
- Helius Enhanced Transactions backfill, conservative ambiguous-swap rejection, persisted wallet outcomes and funding evidence.
- Actor/Funding Graph with effective-wallet count, service-funder hub downweighting, stale co-buy expiry and 1000-wallet sparse-graph safeguards.
- Probabilistic clan/cohort discovery with weighted community splitting so bridge wallets do not merge separate groups.
- Optional FomoScan Pump leaderboard/callout discovery; FOMO observations are deduplicated and remain context only.
- Launch Integrity, coordinated-dump risk and sellability.
- World Model research layer.
- Real preprocessed FlyWire/FAFB reservoir artifacts plus shuffled/rewired/degree-preserved/random controls; recurrent state isolated per token.
- MiroFish-style local future rollouts, gated to meaningful candidates. Rollouts now consume independent wallet breadth and coordinated-clan risk.
- Reliability-aware Multi-Brain Fusion; correlated modules are grouped rather than simply averaged.
- AI Paper Trader consumes fused state. Untrained heuristic entry is permitted only in PAPER research.
- Risk Governor remains final authority over PAPER entries/adds and can veto liquidity, sellability, manipulation, late entry, slippage, cluster concentration, drawdown and daily loss.
- ENTER/ADD is delayed by configurable T+60 seconds and revalidated at the first verified market event at/after due time.
- PAPER cash/open positions, delayed pending signals, Smart Capital positions/state and research evidence survive restarts.
- Daily PAPER spend/loss counters reset by UTC day.
- Current Pump fee schedule is modeled for bonding curve, canonical PumpSwap SOL/USDC tiers and noncanonical pools; unknown Pump tier data uses a conservative fallback.
- Solana base network fee inputs are modeled and failed simulated transactions can still charge their network fee.
- Executable-runner dataset builder, chronological calibrated Genesis training and expanding walk-forward evaluation.
- Component ablation harness and dashboard panels for candidates, fusion, MiroFish/FlyWire, Pump discovery, TRUE smart wallets, cohorts and open PAPER swings.

## Latest verification
GitHub Actions run 153 at commit cf1cdc51e83922a057350bac65703fda6cb6572f:
- Python: 68 passed.
- Demo backtest smoke: success.
- Component ablation smoke: success.
- Frontend production build: success.

The bundled demo currently produces no fills. This is not treated as evidence of failure or success: it is too small to satisfy the stricter Smart Capital gates reliably.

## External activation
To collect useful real point-in-time research data:
- HELIUS_API_KEY is required for real Solana shadow/history enrichment.
- FOMOSCAN_API_KEY is optional. It adds automatic current Pump leaderboard/callout discovery; without it the system can still qualify wallets discovered organically on-chain.
Never commit or paste secrets into chat.

## Scientific status
IMPLEMENTED and TESTED does not mean VALIDATED EDGE. Genesis is still UNTRAINED unless an artifact exists. MiroFish, FlyWire and FOMO are experimental components and must earn promotion through chronological walk-forward/OOS/shadow/PAPER evidence.
