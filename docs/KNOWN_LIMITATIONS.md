# Known Limitations

- No validated trained Genesis or World Model artifact currently ships with v0.2. Calibrated-looking X2/X5/etc outputs must remain unavailable until training succeeds.
- MiroFish is a local MiroFish-style scenario simulator, not an external MiroFish service integration and not evidence of foresight.
- MiroFish PAPER/SHADOW caching is an efficiency optimization; BACKTEST/REPLAY disables that shortcut and executes deterministic full rollout counts.
- FlyWire is an experimental reservoir. Its real FAFB topology and randomized controls are present, but incremental trading value is unproven.
- Early Smart Capital Formation is an experimental challenger. It is designed to study earlier entry timing; it is not a validated alpha source and does not bypass Smart Capital confirmation or Risk Governor rules.
- FomoScan is optional. Without FOMOSCAN_API_KEY the system cannot instantly import that provider's current Pump leaderboard/callouts; it can still discover and qualify wallets organically through live on-chain activity.
- Pump/KOL discovery never makes a wallet Smart Capital automatically; historical on-chain quality, strategy, conviction and independence still govern its weight.
- Wallet research priority is a resource-allocation heuristic, not a trading signal. Its weights require real provider-budget/coverage validation.
- Cohorts/clans are probabilistic behavioral/funding communities, not claims of common real-world ownership or insider status.
- Clan alpha/risk separation is heuristic until validated OOS. Same-funder concentration, independence and community structure reduce false "top clan" promotion but do not prove coordination.
- Current Pump fee logic follows the versioned schedule encoded in runner_genesis/fees.py. Fee schedules can change and should be re-verified before interpreting long PAPER runs.
- Solana network-fee accounting uses configured lamport inputs and observed SOL/USD when available; route-specific compute-unit priority bidding remains simplified.
- Route-specific liquidity depth beyond the current impact/partial-fill model is still an approximation.
- Historical wallet-quality accuracy is limited by how much Helius history has been collected and successfully reconstructed.
- The project has 1000-wallet graph safeguards, but sustained end-to-end provider/load performance with 500-1000 actively refreshed wallets still needs real-world soak testing.
- The bundled demo is too small to validate alpha or profitability.
