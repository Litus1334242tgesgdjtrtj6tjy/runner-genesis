# Known Limitations

- No validated trained Genesis or World Model artifact ships with v0.2.
- No direct Pump.fun leaderboard scraper/API adapter is hardcoded because provider endpoints/eligibility can change; snapshots can be ingested through a stable internal API/provider interface.
- FOMO has no mandatory external social provider and is disabled by default.
- MiroFish is a local MiroFish-style simulator, not an external MiroFish service integration.
- Route-specific live DEX fee schedules are not yet versioned by venue/effective date.
- Failed-transaction network-fee accounting remains simplified in the PAPER execution model.
- Current reference process is in-memory for active state; append-only database snapshots provide research persistence but full restart hydration has not yet been implemented.
- Wallet PnL quality depends on resolved historical observations/backfill data; newly observed wallets correctly remain low-confidence.
- Cohorts/clans are probabilistic behavioral clusters, not identity claims.
- Large-scale 500–1000 wallet performance has not yet been load-tested.
