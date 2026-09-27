from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
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
    """Probabilistic relationship graph; it never asserts real-world identity."""

    def __init__(self, coevent_window_seconds: int = 120) -> None:
        self.graph = nx.Graph()
        self.recent_by_token: dict[str, list[MarketEvent]] = defaultdict(list)
        self.funder_to_wallets: dict[str, set[str]] = defaultdict(set)
        self.wallet_to_funders: dict[str, set[str]] = defaultdict(set)
        self.coevent_window = timedelta(seconds=coevent_window_seconds)

    def observe(self, e: MarketEvent) -> None:
        if e.wallet:
            self.graph.add_node(e.wallet, kind="wallet")
        if e.event_type == EventType.WALLET_FUNDED and e.wallet and e.counterparty:
            f = f"funder:{e.counterparty}"
            self.graph.add_node(f, kind="funder")
            self.graph.add_edge(f, e.wallet, relation="FUNDS", confidence=float(e.confidence), last_seen=e.timestamp)
            self.funder_to_wallets[e.counterparty].add(e.wallet)
            self.wallet_to_funders[e.wallet].add(e.counterparty)
            siblings = self.funder_to_wallets[e.counterparty]
            for other in siblings:
                if other != e.wallet:
                    self._link(e.wallet, other, "SHARES_FUNDER", 0.82, e.timestamp)
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
        self.graph.add_edge(f, wallet, relation="FUNDS", confidence=max(0.0, min(1.0, float(confidence))), last_seen=ts)
        self.funder_to_wallets[funder].add(wallet)
        self.wallet_to_funders[wallet].add(funder)
        for other in self.funder_to_wallets[funder]:
            if other != wallet:
                self._link(wallet, other, "SHARES_FUNDER", min(0.95, 0.75 + 0.20 * float(confidence)), ts)

    def _link(self, a: str, b: str, relation: str, confidence: float, ts: datetime) -> None:
        if not a or not b or a == b:
            return
        if self.graph.has_edge(a, b):
            d = self.graph[a][b]
            old = float(d.get("confidence", 0.0))
            d["confidence"] = min(0.99, 1 - (1 - old) * (1 - confidence))
            d["last_seen"] = ts
            d["relation"] = relation if d.get("relation") == relation else "MULTI"
        else:
            self.graph.add_edge(a, b, relation=relation, confidence=confidence, last_seen=ts)

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

    def _same_funder_concentration(self, wallets: list[str]) -> float:
        unique = set(wallets)
        if len(unique) < 2:
            return 0.0
        max_group = 1
        for funded in self.funder_to_wallets.values():
            max_group = max(max_group, len(unique.intersection(funded)))
        return max_group / len(unique)

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
        return {
            "raw_wallet_count": float(n),
            "effective_wallet_count": eff,
            "independence_ratio": eff / n,
            "cohort_concentration": float(concentration),
            "same_funder_concentration": float(self._same_funder_concentration(unique)),
        }

    def token_cluster_features(self, token_mint: str) -> dict[str, float]:
        wallets = [e.wallet for e in self.recent_by_token.get(token_mint, []) if e.wallet]
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
