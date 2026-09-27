# Test Results

LATEST VERIFIED CODE CHECKPOINT:
48f3f57b54914ca545debf7201e32b8e0a8de960

GitHub Actions:
- Python pytest: **53 passed**
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


Additional coverage added after the earlier checkpoint includes:
- FlyWire state isolation per token
- Pump snapshot freshness and future-leakage prevention
- shared-funder service-hub downweighting/scalability
- swap-proceeds exclusion from funding evidence
- token creation vs migration normalization
- Helius-only research refresh
- FOMO callout deduplication
- daily paper accounting reset
- PAPER portfolio restoration after restart
- executable-runner future labels
- chronological calibrated Genesis training
- expanding walk-forward evaluation
