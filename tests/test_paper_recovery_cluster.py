from datetime import datetime, timezone, timedelta

from runner_genesis.paper_recovery import recover_pending_specs


def test_recovered_pending_signal_keeps_cluster_metadata():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    updates = [{
        "token_mint": "M",
        "observed_at": t0,
        "update_type": "PENDING_ENTER",
        "payload": {
            "due_time": t0 + timedelta(seconds=60),
            "amount_eur": 10.0,
            "fusion_confidence": 0.7,
            "dominant_actor_cluster_id": "actor-cluster-signal",
            "dominant_actor_cluster_fraction": 0.8,
        },
    }]
    specs = recover_pending_specs(updates, [], 60)
    assert len(specs) == 1
    features = specs[0]["signal_features"]
    assert features["dominant_actor_cluster_id"] == "actor-cluster-signal"
    assert features["dominant_actor_cluster_fraction"] == 0.8
