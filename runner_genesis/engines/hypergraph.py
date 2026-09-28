from __future__ import annotations
from collections import defaultdict
from ..domain.events import MarketEvent, EventType

class TemporalHypergraphState:
    """Lightweight typed higher-order event store. It preserves multi-entity events without pairwise-only collapse."""
    def __init__(self, max_edges_per_token:int=2000) -> None:
        self.edges=defaultdict(list)
        self.max_edges=max_edges_per_token

    def observe(self,e:MarketEvent) -> None:
        entities=[f"token:{e.token_mint}"]
        if e.wallet: entities.append(f"wallet:{e.wallet}")
        if e.counterparty: entities.append(f"counterparty:{e.counterparty}")
        for x in e.metadata.get("related_wallets",[]) or []:
            entities.append(f"wallet:{x}")
        self.edges[e.token_mint].append((e.timestamp,e.event_type.value,tuple(dict.fromkeys(entities))))
        if len(self.edges[e.token_mint])>self.max_edges:
            del self.edges[e.token_mint][:-self.max_edges]

    def features(self,mint:str,now) -> dict[str,float]:
        arr=[x for x in self.edges.get(mint,[]) if 0 <= (now-x[0]).total_seconds() <= 300]
        orders=[len(x[2]) for x in arr]
        higher=sum(1 for o in orders if o>=4)
        return {"hyperedge_count_5m":float(len(arr)),"higher_order_edge_fraction":higher/max(len(arr),1),"mean_hyperedge_order":sum(orders)/max(len(orders),1)}
