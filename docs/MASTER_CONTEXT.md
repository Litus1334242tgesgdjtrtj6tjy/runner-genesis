# RUNNER GENESIS Ω — Master Context

## Purpose
RUNNER GENESIS Ω is a PAPER/SHADOW research laboratory for detecting early Solana memecoin runner formation and managing simulated positions. It is **not** a whale copy-trader. The core question is whether an independent, high-quality smart-capital formation is emerging, whether an executable entry still exists, whether the runner is persisting, and when distribution invalidates the thesis.

## Non-negotiable rules
- `LIVE_TRADING=false` by default and no live transaction sender/private-key handling exists.
- Mint address is asset identity. Symbols/tickers are never identity.
- All historical features are point-in-time. No future leakage.
- Missing data is `None`/`UNKNOWN`, not a fabricated zero.
- Untrained models must not display plausible-looking calibrated probabilities.
- Risk Governor outranks AI Paper Trader and every experimental model.
- Advanced components are hypotheses; promotion requires walk-forward/OOS evidence and executable net-return improvement.

## Canonical flow
Solana event stream → Candidate Universe Gate → Event Digital Twin → Actor/Funding graph → Wallet Quality → Smart Capital positions/strategy/conviction/accumulation → weighted independent consensus → Token Quality → Launch Integrity → Market Acceleration/Hawkes/graph engines → Runner Genesis → World Model → optional MiroFish-style rollouts → Persistence/Distribution → Executable Alpha → AI Paper Trader → Risk Governor → delayed PAPER execution → Post-trade review.

## Smart Capital
Wallet source discovery (Pump official/top trader, KOL/community/FOMO) is only discovery context. On-chain history must qualify a wallet before it receives meaningful weight. Consensus uses wallet quality × strategy match × conviction × freshness/continued holding × independence, with raw wallet count corrected into `EFFECTIVE_WALLET_COUNT` using probabilistic Actor/Funding relationships.

## Pump cohorts / clans
The software may infer `ACTOR_CLUSTER`, `FUNDING_CLUSTER`, `TRADING_COHORT` or `PUMPFUN_COHORT` from shared funders, direct transfers and synchronized/repeated behavior. These are probabilistic clusters and must never be represented as proven real-world ownership/identity.

## Launch Integrity
The engine models concentration/manipulation/dump/sellability risk without automatically calling a token a scam. Internal states include `MANIPULATED_LAUNCH`, `COORDINATED_DUMP_RISK`, `CAUTION`, `ACCEPTABLE`, and `INSUFFICIENT_DATA`.

## MiroFish
`MiroFishRolloutEngine` is an **experimental local MiroFish-style multi-agent scenario simulator**, disabled by default. It does not call an external MiroFish service and does not claim to predict the future. Outputs are explicitly simulation frequencies/proxies unless later calibrated empirically.

## FOMO / attention
FOMO is optional and disabled by default. External observations can be ingested through the API and used as discovery/context/confirmation/persistence evidence. Core operation remains ON-CHAIN FIRST.

## FlyWire / quantum-inspired
Both remain experimental and independently disable-able. FlyWire must be compared against shuffled/rewired/degree-preserved/random reservoirs. No component is promoted because it is novel.

## Paper execution
Signal time and execution time are separate. ENTER/ADD can be queued for `execution_delay_seconds`; the fill uses the first verified market observation at or after that delay, plus modeled slippage/impact/fees/latency/failure/partial fill. No ATH/fantasy fills.
