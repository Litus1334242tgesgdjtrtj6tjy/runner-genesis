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
