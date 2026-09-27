# Test Results

LATEST VERIFIED CODE CHECKPOINT:
cf1cdc51e83922a057350bac65703fda6cb6572f

GitHub Actions run 153:
- Python pytest: **68 passed in 5.17s**
- Demo backtest smoke: **success**
- Component ablation smoke: **success**
- Frontend production build: **success**

Coverage includes:
- exact candidate gate and point-in-time behavior;
- conservative Helius swap/transfer normalization;
- creation vs migration;
- swap proceeds excluded from funding evidence;
- wallet history reconstruction and no-future-leakage;
- Smart Capital position/add/reduce/exit, accumulation, conviction, strategy and entry distance;
- 30-day Smart Capital / emerging wallets;
- restart hydration for wallet outcomes, funding evidence, Pump snapshots, Smart Capital positions/state, PAPER fills and delayed signals;
- Pump snapshot freshness and top-wallet wave independence;
- actor/cohort effective wallet count, service-funder downweighting, stale co-buy expiry and 1000-wallet sparse behavior;
- weighted community splitting for bridged wallet groups;
- Launch Integrity;
- FOMO dedupe and point-in-time filtering;
- FlyWire preprocessing and per-token state isolation;
- deterministic/gated MiroFish rollouts including independent-breadth and coordinated-clan inputs;
- Multi-Brain Fusion;
- PAPER-only untrained research entry gating;
- Risk Governor and correlated-cluster veto;
- T+60 delayed PAPER entry;
- current Pump protocol fee tiering;
- Solana network fee accounting, including failed PAPER transactions;
- executable closed-trade metrics and executable-runner future labels;
- calibrated chronological Genesis training and expanding walk-forward evaluation;
- safe component-ablation configurations.

Current demo backtest remains intentionally non-diagnostic for profitability because it contains only a very small synthetic/replay sample.
