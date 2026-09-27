# Test Results

Latest local test run:

python -m pytest -q

Result: **19 passed**.

Added coverage includes:
- TRANSFER != SELL
- wallet-token position add/reduce/exit
- smart-capital bounded features
- related-wallet effective count
- Launch Integrity ordering
- Pump leaderboard point-in-time snapshots/rank dynamics
- SQLAlchemy research-table creation
- MiroFish deterministic seeded rollouts
- MiroFish disabled fallback
- untrained Genesis does not emit fake X2/X5 probabilities

Existing asset gate, point-in-time, Capital Surprise, execution, Risk Governor, FlyWire preprocessing, shadow forwarding and end-to-end replay tests remain passing.

Demo backtest after integration: 35 events, 35 decisions, ending equity €300, no runtime failure.
