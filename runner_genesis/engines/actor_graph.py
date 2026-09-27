from __future__ import annotations
from collections import defaultdict, deque
from datetime import datetime, timedelta
from itertools import combinations
import math
import networkx as nx
from ..domain.events import MarketEvent, EventType


BUY_EVENTS = {
    EventType.BUY,
    EventType.RUNNER_HOLDER_ENTRY,
    EventType.RUNNER_HOLDER_ADD,
    EventType.SMART_WALLET_NEW_ENTRY,
    EventType.SMART_WALLET_ADD,
}


class ActorGraphEngine:
    """Probabilistic relationship graph; it never asserts real-world identity.

    Relation evidence is kept separately. Shared-funder evidence is automatically
    downweighted when the funder behaves like a high-degree hub (for example an exchange
    or distribution service), preventing one common service wallet from manufacturing a
    fake "clan".
    """

    def __init__(self, coevent_window_seconds: int = 120, max_funder_pair_expansion: int = 64, max_seen_events: int = 500_000) -> None:
        self.graph = nx.Graph()
        self.recent_by_token: dict[str, list[MarketEvent]] = defaultdict(list)
        self.funder_to_wallets: dict[str, set[str]] = defaultdict(set)
        self.wallet_to_funders: dict[str, set[str]] = defaultdict(set)
        self.hub_funders: set[str] = set()
        self.coevent_window = timedelta(seconds=coevent_window_seconds)
        self.max_funder_pair_expansion = max(8, int(max_funder_pair_expansion))
        self.max_seen_events = max(10_000, int(max_seen_events))
        self._seen_event_ids: set[str] = set()
        self._seen_event_order: deque[str] = deque()

    @staticmethod
    def _combine(confs) -> float:
        miss = 1.0
        for c in confs:
            miss *= 1.0 - max(0.0, min(0.99, float(c)))
        return min(0.99, 1.0 - miss)

    def _ensure_evidence(self, a: str, b: str) -> dict[str, float]:
        if not self.graph.has_edge(a, b):
            self.graph.add_edge(a, b, confidence=0.0, relation="UNKNOWN", evidence={})
        d = self.graph[a][b]
        evidence = d.get("evidence")
        if not isinstance(evidence, dict):
            old_relation = str(d.get("relation") or "UNKNOWN")
            old_conf = float(d.get("confidence", 0.0) or 0.0)
            evidence = {} if old_relation == "UNKNOWN" else {old_relation: old_conf}
            d["evidence"] = evidence
        return evidence

    def _recompute_edge(self, a: str, b: str, ts: datetime) -> None:
        if not self.graph.has_edge(a, b):
            return
        d = self.graph[a][b]
        evidence = self._ensure_evidence(a, b)
        positive = {k: float(v) for k, v in evidence.items() if float(v) > 0.0}
        d["confidence"] = self._combine(positive.values()) if positive else 0.0
        d["relation"] = next(iter(positive)) if len(positive) == 1 else ("MULTI" if positive else "UNKNOWN")
        d["last_seen"] = ts

    def _set_relation_confidence(self, a: str, b: str, relation: str, confidence: float, ts: datetime) -> None:
        if not a or not b or a == b:
            return
        self.graph.add_node(a, kind=self.graph.nodes.get(a, {}).get("kind", "wallet"))
        self.graph.add_node(b, kind=self.graph.nodes.get(b, {}).get("kind", "wallet"))
        evidence = self._ensure_evidence(a, b)
        evidence[relation] = max(0.0, min(0.99, float(confidence)))
        self._recompute_edge(a, b, ts)

    def _shared_funder_confidence(self, funder: str) -> float:
        degree = max(2, len(self.funder_to_wallets.get(funder, ())))
        # Two-wallet shared funding is strong evidence. As a funder touches many wallets,
        # the evidence decays toward service/hub behavior instead of growing stronger.
        hub_factor = math.sqrt(2.0 / degree)
        return max(0.08, min(0.92, 0.92 * hub_factor))

    def _refresh_funder_sibling_edges(self, funder: str, ts: datetime) -> None:
        siblings = sorted(self.funder_to_wallets.get(funder, ()))
        if len(siblings) > self.max_funder_pair_expansion:
            if funder in self.hub_funders:
                return
            self.hub_funders.add(funder)
            sibling_set = set(siblings)
            for a, b, data in list(self.graph.edges(data=True)):
                if a not in sibling_set or b not in sibling_set:
                    continue
                evidence = data.get("evidence")
                if not isinstance(evidence, dict) or "SHARES_FUNDER" not in evidence:
                    continue
                common = self.wallet_to_funders.get(a, set()).intersection(self.wallet_to_funders.get(b, set()))
                eligible = [
                    x for x in common
                    if x != funder and len(self.funder_to_wallets.get(x, ())) <= self.max_funder_pair_expansion
                ]
                best = max((self._shared_funder_confidence(x) for x in eligible), default=0.0)
                self._set_relation_confidence(a, b, "SHARES_FUNDER", best, ts)
            return

        confidence = self._shared_funder_confidence(funder)
        for a, b in combinations(siblings, 2):
            common = self.wallet_to_funders.get(a, set()).intersection(self.wallet_to_funders.get(b, set()))
            eligible = [
                x for x in common
                if len(self.funder_to_wallets.get(x, ())) <= self.max_funder_pair_expansion
            ]
            best = max((self._shared_funder_confidence(x) for x in eligible), default=0.0)
            self._set_relation_confidence(a, b, "SHARES_FUNDER", best or confidence, ts)

    def _accept_event_once(self, event_id: str | None) -> bool:
        if not event_id:
            return True
        if event_id in self._seen_event_ids:
            return False
        self._seen_event_ids.add(event_id)
        self._seen_event_order.append(event_id)
        if len(self._seen_event_order) > self.max_seen_events:
            expired = self._seen_event_order.popleft()
            self._seen_event_ids.discard(expired)
        return True

    def observe(self, e: MarketEvent) -> None:
        if not self._accept_event_once(e.event_id):
            return
        if e.wallet:
            self.graph.add_node(e.wallet, kind="wallet")
        if e.event_type == EventType.WALLET_FUNDED and e.wallet and e.counterparty:
            f = f"funder:{e.counterparty}"
            self.graph.add_node(f, kind="funder")
            self.graph.add_edge(
                f, e.wallet,
                relation="FUNDS",
                confidence=float(e.confidence),
                last_seen=e.timestamp,
                evidence={"FUNDS": float(e.confidence)},
            )
            self.funder_to_wallets[e.counterparty].add(e.wallet)
            self.wallet_to_funders[e.wallet].add(e.counterparty)
            self._refresh_funder_sibling_edges(e.counterparty, e.timestamp)
        if e.event_type == EventType.TRANSFER and e.wallet and e.counterparty:
            self._link(e.wallet, e.counterparty, "DIRECT_TRANSFER", min(0.9, 0.45 + 0.45 * e.confidence), e.timestamp)
        if e.event_type in BUY_EVENTS and e.wallet:
            arr = self.recent_by_token[e.token_mint]
            cutoff = e.timestamp - self.coevent_window
            arr[:] = [x for x in arr if x.timestamp >= cutoff]
            for prev in arr:
                if prev.wallet and prev.wallet != e.wallet:
                    dt = abs((e.timestamp - prev.timestamp).total_seconds())
                    conf = max(0.10, 0.60 * (1.0 - dt / max(self.coevent_window.total_seconds(), 1)))
                    self._link(prev.wallet, e.wallet, "CO_BUYS", conf, e.timestamp)
            arr.append(e)

    def observe_funding_link(self, wallet: str, funder: str, ts: datetime, confidence: float = 0.90) -> None:
        """Ingest historical funding evidence without manufacturing a token event."""
        if not wallet or not funder or wallet == funder:
            return
        self.graph.add_node(wallet, kind="wallet")
        f = f"funder:{funder}"
        self.graph.add_node(f, kind="funder")
        self.graph.add_edge(
            f, wallet,
            relation="FUNDS",
            confidence=max(0.0, min(1.0, float(confidence))),
            last_seen=ts,
            evidence={"FUNDS": max(0.0, min(1.0, float(confidence)))},
        )
        self.funder_to_wallets[funder].add(wallet)
        self.wallet_to_funders[wallet].add(funder)
        self._refresh_funder_sibling_edges(funder, ts)

    def _link(self, a: str, b: str, relation: str, confidence: float, ts: datetime) -> None:
        if not a or not b or a == b:
            return
        evidence = self._ensure_evidence(a, b)
        old = float(evidence.get(relation, 0.0) or 0.0)
        # Repeated independent observations of the same relation accumulate but remain
        # bounded. Shared-funder uses exact dynamic confidence and is handled separately.
        if relation == "SHARES_FUNDER":
            evidence[relation] = max(0.0, min(0.99, float(confidence)))
        else:
            evidence[relation] = min(0.99, 1.0 - (1.0 - old) * (1.0 - float(confidence)))
        self._recompute_edge(a, b, ts)

    def link_confidence(self, a: str, b: str) -> float:
        if not self.graph.has_edge(a, b):
            return 0.0
        return float(self.graph[a][b].get("confidence", 0.0))

    def independence_factor(self, wallet: str, peers: list[str]) -> float:
        rel = [self.link_confidence(wallet, p) for p in peers if p != wallet]
        if not rel:
            return 1.0
        strongest = max(rel)
        mean = sum(rel) / len(rel)
        return max(0.15, min(1.0, 1.0 - 0.65 * strongest - 0.20 * mean))

    def effective_wallet_count(self, wallets: list[str]) -> float:
        unique = list(dict.fromkeys(w for w in wallets if w))
        return float(sum(self.independence_factor(w, unique) for w in unique))

    def _same_funder_concentration_pair(self, wallets: list[str]) -> tuple[float, float]:
        unique = set(wallets)
        if len(unique) < 2:
            return 0.0, 0.0
        raw = 0.0
        adjusted = 0.0
        for funder, funded in self.funder_to_wallets.items():
            matched = len(unique.intersection(funded))
            if matched < 2:
                continue
            share = matched / len(unique)
            raw = max(raw, share)
            adjusted = max(adjusted, share * self._shared_funder_confidence(funder) / 0.92)
        return min(1.0, raw), min(1.0, adjusted)

    def _same_funder_concentration(self, wallets: list[str]) -> float:
        return self._same_funder_concentration_pair(wallets)[1]

    def cohort_features(self, wallets: list[str]) -> dict[str, float]:
        unique = list(dict.fromkeys(w for w in wallets if w))
        n = len(unique)
        if n == 0:
            return {
                "raw_wallet_count": 0.0,
                "effective_wallet_count": 0.0,
                "independence_ratio": 0.0,
                "cohort_concentration": 0.0,
                "same_funder_concentration": 0.0,
                "same_funder_concentration_raw": 0.0,
            }
        eff = self.effective_wallet_count(unique)
        if n == 1:
            concentration = 0.0
        else:
            sub = self.graph.subgraph(unique).copy()
            weak = [(a, b) for a, b, d in sub.edges(data=True) if float(d.get("confidence", 0.0)) < 0.55]
            sub.remove_edges_from(weak)
            components = [len(c) for c in nx.connected_components(sub)] if len(sub) else []
            concentration = max(components, default=1) / n
        raw_funder, adjusted_funder = self._same_funder_concentration_pair(unique)
        return {
            "raw_wallet_count": float(n),
            "effective_wallet_count": eff,
            "independence_ratio": eff / n,
            "cohort_concentration": float(concentration),
            "same_funder_concentration": float(adjusted_funder),
            "same_funder_concentration_raw": float(raw_funder),
        }

    def token_cluster_features(self, token_mint: str, as_of: datetime | None = None) -> dict[str, float]:
        arr = self.recent_by_token.get(token_mint, [])
        if as_of is not None:
            cutoff = as_of - self.coevent_window
            arr[:] = [e for e in arr if cutoff <= e.timestamp <= as_of]
        wallets = [e.wallet for e in arr if e.wallet]
        unique = list(dict.fromkeys(wallets))
        cohort = self.cohort_features(unique)
        if len(unique) < 2:
            return {
                "cluster_density": 0.0,
                "cluster_mean_confidence": 0.0,
                "cluster_size": float(len(unique)),
                **cohort,
            }
        sub = self.graph.subgraph(unique)
        confs = [float(d.get("confidence", 0)) for _, _, d in sub.edges(data=True)]
        return {
            "cluster_density": float(nx.density(sub)) if len(sub) > 1 else 0.0,
            "cluster_mean_confidence": float(sum(confs) / len(confs)) if confs else 0.0,
            "cluster_size": float(len(unique)),
            **cohort,
        }
