# Model Registry

| Component | Status | PAPER config | Interpretation |
|---|---|---:|---|
| Runner Genesis | UNTRAINED unless artifact exists | ON | Heuristic research score; calibrated probabilities stay N/A |
| Smart Capital | RESEARCH HEURISTIC | ON | Quality/strategy/conviction/accumulation/independence |
| Wallet Discovery Priority | RESEARCH BUDGET HEURISTIC | ON | Chooses which wallets deserve scarce historical-data spend; never a BUY signal |
| Probabilistic Clan Engine | RESEARCH HEURISTIC | ON | Community structure with separate alpha and coordination-risk scores |
| Early Smart Capital Formation | EXPERIMENTAL CHALLENGER | ON | Measures growth in independent Smart Capital before excessive price extension |
| Multi-Brain Fusion | RESEARCH HEURISTIC | ON | Reliability-aware fused research score, not probability |
| World Model | UNTRAINED unless artifact exists | ON | Future-state scores |
| MiroFish-style rollout | EXPERIMENTAL | ON, gated/cached | Local scenario simulation; deterministic full rollouts in BACKTEST/REPLAY |
| FlyWire FAFB reservoir | EXPERIMENTAL | ON | Fixed sparse reservoir; randomized controls required |
| FOMO context | EXPERIMENTAL CONTEXT | ON | Requires observations/provider; cannot trigger entry alone |
| Pump discovery | DISCOVERY | ON | Top-wallet/KOL context; on-chain qualification mandatory |
| Quantum-inspired graph | EXPERIMENTAL | OFF | Classical controls required |
| Hawkes cascade | RESEARCH FEATURE | ON | Self-excitation/cascade state, no independent alpha claim |
| Launch Integrity | RESEARCH RISK | ON | Manipulation/dump/sellability evidence, not fraud classification |
| Runner Persistence | RESEARCH HEURISTIC | ON | Hold/distribution state |
| Risk Governor | RULE ENGINE | ON | Final authority over PAPER entry/position actions |

Promotion states are distinct:
IMPLEMENTED -> TESTED -> OOS VALIDATED -> SHADOW VALIDATED -> PAPER PROMOTED.

No experimental brain or challenger is considered promoted merely because it is enabled for PAPER research.
