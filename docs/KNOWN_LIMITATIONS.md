# Known Limitations

- Current Smart Capital quality reuses the existing resolved-history mechanism; it is not yet a complete on-chain accounting ledger.
- Wallet liquid capital is intentionally not invented when unavailable.
- Actor independence is a probabilistic graph heuristic, not proof of common ownership.
- MiroFish is currently an internal role-based stochastic rollout implementation inspired by the concept, not an external MiroFish service integration.
- FOMO is disabled by default and has no external provider enabled.
- Pump discovery currently accepts timestamped provider observations; no undocumented Pump.fun endpoint is fabricated.
- Genesis/World fallback values are research scores/estimates only.
- execution_delay_seconds exists in config; full event-scheduled delayed entry remains pending.
