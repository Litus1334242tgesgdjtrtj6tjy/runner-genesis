# Current State

VERSION: 0.2.0-development
BRANCH: work/v0.2-smart-capital-world-model
LATEST VERIFIED CODE CHECKPOINT: be386666df00621902918aed9c818d5c5cd7897d
SAFE_MODE_STATUS: PAPER / SHADOW / BACKTEST only. LIVE_TRADING=false. No private-key sender exists.

## Implemented
- Exact-mint candidate gate, conservative BUY/SELL normalization and UNKNOWN-data semantics.
- Smart Capital wallet-token positions, strategy/style, conviction, accumulation, entry distance, persistence/distribution and restart hydration.
- TRUE_SMART_CAPITAL_30D and Emerging Smart Wallet scoring from resolved point-in-time history.
- Wallet research priority engine for scarce Helius budget using current Pump rank, rank momentum, 30d Smart Capital, Emerging score, recency, independence, probabilistic-clan quality, data gap and source confidence.
- Stale/future Pump ranks cannot revive research priority after point-in-time freshness expiry.
- Pump/KOL discovery snapshots with as-of rank dynamics, stale-snapshot expiry and independent top-wallet wave features.
- Helius-only organic qualification of wallets observed in live Pump/PumpSwap traffic.
- Helius Enhanced Transactions backfill, conservative ambiguous-swap rejection, persisted wallet outcomes and funding evidence.
- Actor/Funding Graph with effective-wallet count, service-funder hub downweighting, stale co-buy expiry, historical-event dedupe and 1000-wallet sparse-graph safeguards.
- Probabilistic clan/cohort discovery with weighted community splitting. Clan alpha quality is separated from coordination risk so dense same-funder clusters do not rank as superior alpha merely because they are coordinated.
- Optional FomoScan Pump leaderboard/callout discovery; FOMO observations are deduplicated and remain context only.
- Launch Integrity, coordinated-dump risk and sellability.
- Experimental Early Smart Capital Formation challenger: detects increasing independent Smart Capital before excessive price extension. It is research context, not a direct BUY trigger.
- World Model research layer.
- Real preprocessed FlyWire/FAFB reservoir artifacts plus shuffled/rewired/degree-preserved/random controls; recurrent state isolated per token.
- MiroFish-style local future rollouts, gated to meaningful candidates. It now consumes independent wallet breadth, coordinated-clan risk and Early Formation context.
- MiroFish PAPER/SHADOW deep-path caching avoids repeated near-identical rollouts during event bursts.
- MiroFish BACKTEST/REPLAY runs deterministically with an exact rollout count; wall-clock machine speed cannot truncate research results.
- Reliability-aware Multi-Brain Fusion; correlated modules are grouped rather than simply averaged.
- AI Paper Trader consumes fused state. Untrained heuristic entry is permitted only in PAPER research.
- Risk Governor remains final authority over PAPER entries/adds and can veto liquidity, sellability, manipulation, late entry, slippage, cluster concentration, drawdown and daily loss.
- ENTER/ADD is delayed by configurable T+60 seconds and revalidated at the first verified market event at/after due time.
- PAPER cash/open positions, delayed pending signals, Smart Capital positions/state and research evidence survive restarts.
- Daily PAPER spend/loss counters reset by UTC day.
- Pump fee schedule and Solana network fee accounting are included in PAPER execution; failed simulated transactions can still incur network cost.
- Executable-runner dataset builder excludes right-censored decisions and keeps future labels out of point-in-time features.
- Chronological calibrated Genesis training, label-availability purging, walk-forward evaluation and expanded precision/recall/F1/PR-AUC/ROC-AUC/Brier/log-loss/ECE metrics.
- Backtest trade metrics include net PnL, ROI, win rate, expectancy, profit factor, drawdown, hold time, MFE/MAE, captured MFE, multi-bagger rates, turnover and costs.
- Component ablation harness and dashboard panels for candidates, Early Formation, fusion, MiroFish/FlyWire, Pump discovery, TRUE smart wallets, clan alpha/risk and open PAPER swings.

## Latest verification
GitHub Actions run 264 at commit be386666df00621902918aed9c818d5c5cd7897d:
- Python: 108 passed.
- Demo backtest smoke: success.
- Component ablation smoke: success.
- Frontend production build: success.

The bundled demo currently produces no fills. This is not evidence of failure or success: it is too small to satisfy the stricter Smart Capital gates reliably.

## External activation
To collect useful real point-in-time research data:
- HELIUS_API_KEY is required for real Solana shadow/history enrichment.
- FOMOSCAN_API_KEY is optional. It adds automatic current Pump leaderboard/callout discovery; without it the system can still qualify wallets discovered organically on-chain.
Never commit or paste secrets into chat.

## Scientific status
IMPLEMENTED and TESTED does not mean VALIDATED EDGE. Genesis is still UNTRAINED unless a trained artifact exists. MiroFish, FlyWire, FOMO and Early Formation remain experimental and must earn promotion through chronological walk-forward/OOS/shadow/PAPER evidence.
