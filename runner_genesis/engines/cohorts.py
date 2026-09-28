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
    by the same real-world person. Large connected components are split with weighted
    modularity so one bridge wallet does not merge several otherwise distinct "clans".
    """

    def __init__(
        self,
        min_edge_confidence: float = 0.55,
        max_edge_age_seconds: float = 30 * 86400,
        modularity_split_size: int = 8,
    ) -> None:
        self.min_edge_confidence = float(min_edge_confidence)
        self.max_edge_age_seconds = float(max_edge_age_seconds)
        self.modularity_split_size = max(4, int(modularity_split_size))

    def _communities(self, g: nx.Graph, min_size: int) -> list[tuple[set[str], str]]:
        out: list[tuple[set[str], str]] = []
        for component in nx.connected_components(g):
            members = set(component)
            if len(members) < min_size:
                continue
            sub = g.subgraph(members)
            if len(members) < self.modularity_split_size or sub.number_of_edges() < len(members):
                out.append((members, "CONNECTED_COMPONENT"))
                continue
            try:
                communities = list(nx.community.greedy_modularity_communities(sub, weight="confidence"))
            except Exception:
                communities = [frozenset(members)]
            accepted = [set(x) for x in communities if len(x) >= min_size]
            if not accepted:
                out.append((members, "CONNECTED_COMPONENT"))
            else:
                out.extend((x, "GREEDY_MODULARITY") for x in accepted)
        return out

    @staticmethod
    def _relation_counts(sub: nx.Graph) -> Counter:
        counts: Counter = Counter()
        for _, _, data in sub.edges(data=True):
            evidence = data.get("evidence")
            if isinstance(evidence, dict):
                for relation, conf in evidence.items():
                    if float(conf or 0.0) > 0:
                        counts[str(relation)] += 1
            else:
                counts[str(data.get("relation") or "UNKNOWN")] += 1
        return counts

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
        for community, method in self._communities(g, int(min_size)):
            members = sorted(community)
            sub = g.subgraph(members)
            confs = [float(d.get("confidence", 0.0) or 0.0) for _, _, d in sub.edges(data=True)]
            relations = self._relation_counts(sub)
            qualities = [float(wallet_metrics.get(w, {}).get("wallet_quality_score") or 0.0) for w in members]
            swings = [float(wallet_metrics.get(w, {}).get("swing_score") or 0.0) for w in members]
            holds = [float(wallet_metrics.get(w, {}).get("hold_score") or 0.0) for w in members]
            effective = float(actor.effective_wallet_count(members))
            breadth = _clip(effective / 4.0)
            avg_quality = sum(qualities) / len(qualities)
            avg_swing = sum(swings) / len(swings)
            avg_hold = sum(holds) / len(holds)
            mean_conf = sum(confs) / len(confs) if confs else 0.0
            density = float(nx.density(sub)) if len(members) > 1 else 0.0
            relation_diversity = _clip(len(relations) / 4.0)
            structure = _clip(0.55 * mean_conf + 0.30 * density + 0.15 * relation_diversity)
            base_alpha = _clip(
                0.32 * avg_quality
                + 0.20 * breadth
                + 0.14 * avg_swing
                + 0.14 * avg_hold
                + 0.20 * structure
            )
            independence_ratio = effective / len(members)
            same_funder = actor._same_funder_concentration(members)
            coordination_risk = _clip(
                0.50 * (1.0 - independence_ratio)
                + 0.35 * same_funder
                + 0.15 * mean_conf * (1.0 - independence_ratio)
            )
            # A dense clan is useful only when it also contains genuine independent
            # breadth. This prevents a highly coordinated same-funder cluster from being
            # ranked as a better alpha cohort merely because its graph is dense.
            alpha_context = _clip(
                base_alpha
                * (0.55 + 0.45 * independence_ratio)
                * (1.0 - 0.50 * same_funder)
            )
            cid = hashlib.sha256("|".join(members).encode()).hexdigest()[:16]
            rows.append({
                "cohort_id": f"cohort:{cid}",
                "members": members,
                "raw_wallet_count": len(members),
                "effective_wallet_count": effective,
                "independence_ratio": independence_ratio,
                "mean_edge_confidence": mean_conf,
                "edge_density": density,
                "relation_diversity": relation_diversity,
                "same_funder_concentration": same_funder,
                "relation_counts": dict(relations),
                "average_wallet_quality": avg_quality,
                "average_swing_score": avg_swing,
                "average_hold_score": avg_hold,
                "cohort_structure_score": structure,
                "cohort_base_alpha_score": base_alpha,
                "cohort_risk_score": coordination_risk,
                "cohort_alpha_score": alpha_context,
                "cohort_score": alpha_context,
                "community_method": method,
                "as_of": as_of,
                "interpretation": "PROBABILISTIC_BEHAVIORAL_COHORT",
            })
        rows.sort(
            key=lambda x: (
                float(x["cohort_score"]),
                float(x["cohort_structure_score"]),
                float(x["effective_wallet_count"]),
            ),
            reverse=True,
        )
        return rows[: max(1, int(limit))]
