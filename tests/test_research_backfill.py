from datetime import datetime, timezone, timedelta

from runner_genesis.domain.events import EventType, MarketEvent
from runner_genesis.engines.actor_graph import ActorGraphEngine
from runner_genesis.engines.cohorts import CohortDiscoveryEngine
from runner_genesis.ingestion.helius_history import EnhancedWalletHistoryNormalizer, WalletOutcomeBuilder
from runner_genesis.state_store import MarketStateStore


WALLET = "Wallet11111111111111111111111111111111111"
POOL = "Pool1111111111111111111111111111111111111"
MINT = "Mint1111111111111111111111111111111111111"


def _swap_buy(ts=1_700_000_000):
    return {
        "type": "SWAP",
        "signature": "buy_sig",
        "timestamp": ts,
        "tokenTransfers": [
            {"mint": MINT, "fromUserAccount": POOL, "toUserAccount": WALLET, "tokenAmount": 100.0},
        ],
        "nativeTransfers": [
            {"fromUserAccount": WALLET, "toUserAccount": POOL, "amount": 1_000_000_000},
        ],
    }


def _swap_sell(ts=1_700_000_600):
    return {
        "type": "SWAP",
        "signature": "sell_sig",
        "timestamp": ts,
        "tokenTransfers": [
            {"mint": MINT, "fromUserAccount": WALLET, "toUserAccount": POOL, "tokenAmount": 100.0},
        ],
        "nativeTransfers": [
            {"fromUserAccount": POOL, "toUserAccount": WALLET, "amount": 2_000_000_000},
        ],
    }


def test_enhanced_history_normalizes_clear_sol_buy_and_sell():
    n = EnhancedWalletHistoryNormalizer()
    buy = n.normalize_swap(WALLET, _swap_buy())
    sell = n.normalize_swap(WALLET, _swap_sell())
    assert len(buy) == 1 and buy[0].event_type == EventType.BUY
    assert buy[0].token_mint == MINT
    assert buy[0].sol_value == 1.0
    assert buy[0].metadata["quote_asset"] == "SOL"
    assert len(sell) == 1 and sell[0].event_type == EventType.SELL
    assert sell[0].sol_value == 2.0


def test_enhanced_history_refuses_ambiguous_token_token_swap():
    tx = _swap_buy()
    tx["nativeTransfers"] = []
    tx["tokenTransfers"].append({
        "mint": "OtherMint111111111111111111111111111111111",
        "fromUserAccount": WALLET,
        "toUserAccount": POOL,
        "tokenAmount": 50.0,
    })
    assert EnhancedWalletHistoryNormalizer().normalize_swap(WALLET, tx) == []


def test_wallet_outcome_builder_resolves_closed_cycle_in_quote_units():
    n = EnhancedWalletHistoryNormalizer()
    events = n.normalize_swap(WALLET, _swap_buy()) + n.normalize_swap(WALLET, _swap_sell())
    outcomes = WalletOutcomeBuilder().build(events)
    assert len(outcomes) == 1
    assert outcomes[0].token_mint == MINT
    assert abs(outcomes[0].realized_return - 1.0) < 1e-9
    assert outcomes[0].hold_seconds == 600


def test_funding_link_and_cohort_discovery_are_probabilistic():
    n = EnhancedWalletHistoryNormalizer()
    funding_tx = {
        "type": "TRANSFER",
        "signature": "fund",
        "timestamp": 1_700_000_000,
        "nativeTransfers": [
            {"fromUserAccount": "FUNDER", "toUserAccount": WALLET, "amount": 2_000_000_000},
        ],
    }
    links = n.funding_links(WALLET, funding_tx)
    assert len(links) == 1
    assert links[0].funder == "FUNDER"

    actor = ActorGraphEngine()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for w in ["A", "B", "C"]:
        actor.observe_funding_link(w, "FUNDER", now, 0.95)
    metrics = {
        w: {"wallet_quality_score": 0.8, "swing_score": 0.7, "hold_score": 0.7}
        for w in ["A", "B", "C"]
    }
    rows = CohortDiscoveryEngine().discover(actor, metrics, now, min_size=2)
    assert len(rows) == 1
    assert rows[0]["raw_wallet_count"] == 3
    assert rows[0]["effective_wallet_count"] < 3
    assert rows[0]["interpretation"] == "PROBABILISTIC_BEHAVIORAL_COHORT"


def test_backfill_wallet_observations_is_deduplicated_and_point_in_time():
    n = EnhancedWalletHistoryNormalizer()
    events = n.normalize_swap(WALLET, _swap_buy()) + n.normalize_swap(WALLET, _swap_sell())
    outcomes = WalletOutcomeBuilder().build(events)
    store = MarketStateStore()
    assert store.backfill_wallet_observations(WALLET, outcomes) == 1
    assert store.backfill_wallet_observations(WALLET, outcomes) == 0
    as_of_before = datetime.fromtimestamp(1_700_000_300, tz=timezone.utc)
    as_of_after = datetime.fromtimestamp(1_700_000_700, tz=timezone.utc)
    assert store.resolved_wallet_history_as_of(WALLET, as_of_before) == []
    assert len(store.resolved_wallet_history_as_of(WALLET, as_of_after)) == 1


def test_swap_proceeds_are_not_funding_links():
    n = EnhancedWalletHistoryNormalizer()
    assert n.funding_links(WALLET, _swap_sell()) == []
