# Model Registry

| Component | Current status | Default | Notes |
|---|---|---:|---|
| Runner Genesis | UNTRAINED unless artifact exists | ON | Heuristic emits `genesis_score`, not fake probabilities |
| World Model | UNTRAINED unless artifact exists | ON | Heuristic outputs named `*_score` |
| MiroFish rollout | EXPERIMENTAL | OFF | Simulation frequencies/proxies only |
| FlyWire reservoir | EXPERIMENTAL | OFF | Must beat randomized controls OOS |
| Quantum-inspired graph | EXPERIMENTAL | OFF | Classical controls required |
| Hawkes cascade | RESEARCH FEATURE | ON | No independent alpha claim |
| Smart Capital consensus | HEURISTIC/RESEARCH | ON | Requires historical wallet data for confidence |
| Launch Integrity | HEURISTIC/RESEARCH | ON | Evidence score, not legal/fraud classification |
