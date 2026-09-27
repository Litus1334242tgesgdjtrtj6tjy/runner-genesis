from datetime import datetime, timezone

from runner_genesis.engines.actor_graph import ActorGraphEngine
from runner_genesis.engines.cohorts import CohortDiscoveryEngine


def test_large_bridged_component_splits_into_dense_communities():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actor = ActorGraphEngine()
    left = [f"L{i}" for i in range(5)]
    right = [f"R{i}" for i in range(5)]
    for group in (left, right):
        for i, a in enumerate(group):
            actor.graph.add_node(a, kind="wallet")
            for b in group[i + 1:]:
                actor._link(a, b, "CO_BUYS", 0.90, now)
    actor._link(left[-1], right[0], "CO_BUYS", 0.56, now)

    metrics = {
        w: {"wallet_quality_score": 0.8, "swing_score": 0.7, "hold_score": 0.7}
        for w in left + right
    }
    rows = CohortDiscoveryEngine(modularity_split_size=8).discover(
        actor, metrics, now, min_size=2, limit=10
    )
    member_sets = {frozenset(r["members"]) for r in rows}
    assert frozenset(left) in member_sets
    assert frozenset(right) in member_sets
    assert all(r["community_method"] == "GREEDY_MODULARITY" for r in rows)



def test_independent_clan_alpha_beats_same_funder_coordination():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    wallets = ["A", "B", "C"]
    metrics = {
        w: {"wallet_quality_score": 0.8, "swing_score": 0.7, "hold_score": 0.7}
        for w in wallets
    }

    independent = ActorGraphEngine()
    for w in wallets:
        independent.graph.add_node(w, kind="wallet")
    independent._link("A", "B", "CO_BUYS", 0.80, now)
    independent._link("B", "C", "CO_BUYS", 0.80, now)
    independent._link("A", "C", "CO_BUYS", 0.80, now)

    coordinated = ActorGraphEngine()
    for w in wallets:
        coordinated.observe_funding_link(w, "ONE_FUNDER", now, 0.95)

    ind = CohortDiscoveryEngine().discover(independent, metrics, now, min_size=2)[0]
    coord = CohortDiscoveryEngine().discover(coordinated, metrics, now, min_size=2)[0]

    assert ind["cohort_risk_score"] < coord["cohort_risk_score"]
    assert ind["cohort_alpha_score"] > coord["cohort_alpha_score"]
    assert ind["cohort_score"] == ind["cohort_alpha_score"]
