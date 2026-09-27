# Test Results

LATEST VERIFIED CODE CHECKPOINT:
be386666df00621902918aed9c818d5c5cd7897d

GitHub Actions run 264:
- Python pytest: **108 passed in 5.46s**
- Demo backtest smoke: **success**
- Component ablation smoke: **success**
- Frontend production build: **success**

Coverage includes:
- exact candidate gate and point-in-time behavior;
- conservative Helius swap/transfer normalization;
- creation vs migration;
- swap proceeds excluded from funding evidence;
- wallet history reconstruction, historical actor dedupe and no-future-leakage;
- Smart Capital position/add/reduce/exit, accumulation, conviction, strategy and entry distance;
- TRUE_SMART_CAPITAL_30D / Emerging Smart Wallet isolation from stale wins;
- wallet research priority, clan-aware priority, stale-rank expiry and future-recency rejection;
- Pump snapshot freshness and top-wallet wave independence;
- actor/cohort effective-wallet count, service-funder downweighting, stale co-buy expiry and 1000-wallet sparse behavior;
- weighted community splitting and independent-clan alpha vs same-funder coordination risk;
- Launch Integrity and holder-diversity population consistency;
- FOMO dedupe and point-in-time filtering;
- FlyWire preprocessing and per-token state isolation;
- MiroFish candidate gating, clan/independence inputs, stable-state PAPER caching and exact deterministic BACKTEST rollouts;
- Early Smart Capital Formation challenger, entry-headroom penalty and out-of-order protection;
- Multi-Brain Fusion;
- PAPER-only untrained research entry gating;
- Risk Governor and correlated-cluster veto;
- T+60 delayed PAPER entry;
- Pump protocol fee tiering and Solana network fee accounting, including failed PAPER transactions;
- PAPER restart recovery and event idempotency;
- executable closed-trade metrics, hold time, MFE/MAE, captured MFE and cost metrics;
- executable-runner future labels with right-censor exclusion;
- calibrated chronological Genesis training, label-availability purge and expanding walk-forward evaluation;
- precision, recall, F1, precision@top-decile, PR-AUC, ROC-AUC, Brier, log-loss and ECE evaluation;
- safe component-ablation configurations;
- bounded/shared exact-mint market enrichment.

Current demo backtest remains intentionally non-diagnostic for profitability because it contains only a very small synthetic/replay sample.
