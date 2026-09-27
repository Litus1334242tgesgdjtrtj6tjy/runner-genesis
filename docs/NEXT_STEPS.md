# Next Steps / Handoff

Read MASTER_CONTEXT.md and CURRENT_STATE.md first.

The implementation bottleneck is now DATA / VALIDATION rather than missing core architecture.

1. Configure a real HELIUS_API_KEY locally in .env and run PAPER/SHADOW long enough to build point-in-time wallet outcomes, funding cohorts and executable token histories.
2. Optionally configure FOMOSCAN_API_KEY locally to enable automatic Pump top-trader/callout discovery. If no key is present, the system degrades safely and keeps on-chain core operation.
3. Inspect /api/research/status, /api/smart-capital/wallets and /api/discovery/cohorts to confirm real data is populating.
4. Build historical EXECUTABLE_RUNNER labels using only information available at decision time plus post-decision labels, with realistic fees/slippage/impact/sellability.
5. Train/calibrate Genesis and future-state models chronologically; keep P_X2/P_X5/etc N/A until this is done.
6. Run expanding/rolling walk-forward evaluation and component ablations. Promote MiroFish/FlyWire/FOMO only if they improve OOS calibration, false positives, lead time and executable net performance.
7. Add larger 500–1000 wallet operational load tests after real provider rate limits are observed.
8. Keep LIVE_TRADING=false.

Continuation command for another ChatGPT conversation:
"Continue RUNNER GENESIS Ω from branch work/v0.2-smart-capital-world-model. Read docs/MASTER_CONTEXT.md, docs/CURRENT_STATE.md and docs/NEXT_STEPS.md, inspect the latest GitHub Actions run, and continue without enabling live trading."
