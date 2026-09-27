from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import hashlib
from typing import Any

import networkx as nx


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


class CohortDiscoveryEngine:
    """Ranks probabilistic wallet cohorts from the Actor Graph.

    A cohort is a behavioral/funding cluster, never a claim that the wallets are controlled
    by the same real-world person.
    """

    def __init__(self, min_edge_confidence: float = 0.55, max_edge_age_seconds: float = 30 * 86400) -> None:
        self.min_edge_confidence = float(min_edge_confidence)
        self.max_edge_age_seconds = float(max_edge_age_seconds)

    def discover(
        self,
        actor,
        wallet_metrics: dict[str, dict[str, Any]],
        as_of: datetime,
        *,
        min_size: int = 2,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        g = nx.Graph()
        cutoff = as_of - timedelta(seconds=self.max_edge_age_seconds)
        for node, data in actor.graph.nodes(data=True):
            if data.get("kind") == "wallet":
                g.add_node(node)
        for a, b, data in actor.graph.edges(data=True):
            if a not in g or b not in g:
                continue
            conf = float(data.get("confidence", 0.0) or 0.0)
            last_seen = data.get("last_seen")
            if conf < self.min_edge_confidence:
                continue
            if isinstance(last_seen, datetime) and last_seen < cutoff:
                continue
            g.add_edge(a, b, **data)

        rows: list[dict[str, Any]] = []
        for component in nx.connected_components(g):
            members = sorted(component)
            if len(members) < int(min_size):
                continue
            sub = g.subgraph(members)
            confs = [float(d.get("confidence", 0.0) or 0.0) for _, _, d in sub.edges(data=True)]
            relations = Counter(str(d.get("relation") or "UNKNOWN") for _, _, d in sub.edges(data=True))
            qualities = [float(wallet_metrics.get(w, {}).get("wallet_quality_score") or 0.0) for w in members]
            swings = [float(wallet_metrics.get(w, {}).get("swing_score") or 0.0) for w in members]
            holds = [float(wallet_metrics.get(w, {}).get("hold_score") or 0.0) for w in members]
            effective = float(actor.effective_wallet_count(members))
            breadth = _clip(effective / 4.0)
            avg_quality = sum(qualities) / len(qualities)
            avg_swing = sum(swings) / len(swings)
            avg_hold = sum(holds) / len(holds)
            mean_conf = sum(confs) / len(confs) if confs else 0.0
            score = _clip(0.35 * avg_quality + 0.20 * breadth + 0.15 * avg_swing + 0.15 * avg_hold + 0.15 * mean_conf)
            cid = hashlib.sha256("|".join(members).encode()).hexdigest()[:16]
            rows.append({
                "cohort_id": f"cohort:{cid}",
                "members": members,
                "raw_wallet_count": len(members),
                "effective_wallet_count": effective,
                "independence_ratio": effective / len(members),
                "mean_edge_confidence": mean_conf,
                "same_funder_concentration": actor._same_funder_concentration(members),
                "relation_counts": dict(relations),
                "average_wallet_quality": avg_quality,
                "average_swing_score": avg_swing,
                "average_hold_score": avg_hold,
                "cohort_score": score,
                "as_of": as_of,
                "interpretation": "PROBABILISTIC_BEHAVIORAL_COHORT",
            })
        rows.sort(key=lambda x: (float(x["cohort_score"]), float(x["effective_wallet_count"])), reverse=True)
        return rows[: max(1, int(limit))]
