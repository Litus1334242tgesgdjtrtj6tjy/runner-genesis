from __future__ import annotations
from collections import deque
import numpy as np

class HistoricalAnalogueEngine:
    """Stores only states observed before the query time. Outcomes may be attached later when resolved."""
    def __init__(self,keys=None,maxlen=200000):
        self.keys=keys or ['capital_surprise','wallet_quality','cluster_density','runner_cascade_r','capital_convergence','smart_money_consensus','token_risk']
        self.rows=deque(maxlen=maxlen)
    def add_resolved(self,timestamp,token_mint,features,outcome:dict):
        self.rows.append((timestamp,token_mint,np.array([float(features.get(k,0) or 0) for k in self.keys],dtype=float),dict(outcome)))
    def query(self,as_of,features,k=5):
        x=np.array([float(features.get(key,0) or 0) for key in self.keys],dtype=float)
        candidates=[r for r in self.rows if r[0] < as_of]
        if not candidates:return []
        arr=np.vstack([r[2] for r in candidates]); scale=np.std(arr,axis=0); scale[scale<1e-6]=1
        d=np.linalg.norm((arr-x)/scale,axis=1); idx=np.argsort(d)[:k]
        return [{'token_mint':candidates[i][1],'distance':float(d[i]),'outcome':candidates[i][3]} for i in idx]
