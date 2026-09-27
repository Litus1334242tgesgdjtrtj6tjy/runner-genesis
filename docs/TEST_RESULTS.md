# Test Results

LATEST VERIFIED CODE CHECKPOINT:
8751dd0b3555864fa73df646393258358995234d

GitHub Actions:
- Python pytest: **35 passed in 3.29s**
- Frontend production build: **success**
- Demo backtest smoke: **success**
- Component ablation smoke: **success**

Latest demo backtest output:
- events: 35
- decisions: 35
- fills: 0
- ending equity: €300
- net PnL: €0
- max drawdown: 0

The absence of fills is expected for this small demo because the stricter Smart Capital confirmation requires quality, strategy, conviction, accumulation and independent breadth.

Coverage now includes:
- exact candidate gate / point-in-time behavior
- Capital Surprise
- paper execution / T+60 delayed entry
- Risk Governor and correlated cohort veto
- FlyWire preprocessing
- Smart Capital position reconstruction
- TRANSFER != SELL
- accumulation / conviction / entry distance
- 30-day Smart Capital windows / emerging wallets
- same-funder independence / effective wallet count
- Pump top-wallet wave independence
- Launch Integrity
- FOMO point-in-time filtering
- deterministic and low-signal-gated MiroFish rollouts
- Multi-Brain Fusion
- PAPER-only untrained research entry gating
- Helius history BUY/SELL normalization
- ambiguous token-token refusal
- wallet outcome reconstruction
- cohort discovery
- wallet backfill dedupe/no-future-leakage
- persisted wallet/funding research hydration after restart
- executable closed-trade metric reconstruction
- safe ablation configurations
