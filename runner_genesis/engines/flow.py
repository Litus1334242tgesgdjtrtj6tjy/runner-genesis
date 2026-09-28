from __future__ import annotations
import numpy as np
from ..domain.state import TokenState
from ..domain.events import EventType

class GraphFlowDynamicsEngine:
    """Graph-flow inspired features over observed capital; no claim of physical market dynamics."""
    def features(self, t: TokenState, now) -> dict[str,float]:
        ev=[e for e in t.events if 0 <= (now-e.timestamp).total_seconds() <= 180]
        buys=np.array([float(e.usd_value or 0) for e in ev if e.event_type in (EventType.BUY,EventType.RUNNER_HOLDER_ENTRY,EventType.RUNNER_HOLDER_ADD)],dtype=float)
        sells=np.array([float(e.usd_value or 0) for e in ev if e.event_type in (EventType.SELL,EventType.RUNNER_HOLDER_REDUCE,EventType.RUNNER_HOLDER_EXIT)],dtype=float)
        source=float(buys.sum())
        sink=float(sells.sum())
        total=max(source+sink,1.0)
        convergence=(source-sink)/total
        coherence=(source/max(len(buys),1))/max((source/max(len(buys),1))+(sink/max(len(sells),1)),1e-9) if len(buys)+len(sells) else 0.5
        instability=float(np.std(np.r_[buys,-sells])/max(np.mean(np.abs(np.r_[buys,-sells])) if len(buys)+len(sells) else 1.0,1e-9)) if len(buys)+len(sells) else 0.0
        return {
          "smart_capital_density":source/180.0,
          "capital_convergence":float(convergence),
          "capital_divergence":float(-min(convergence,0.0)),
          "flow_velocity":float((source-sink)/180.0),
          "flow_coherence":float(coherence),
          "smart_source_strength":source,
          "distribution_sink":sink,
          "flow_instability":instability,
        }
