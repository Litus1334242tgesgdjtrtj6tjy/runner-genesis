from __future__ import annotations
import numpy as np
import networkx as nx
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import expm_multiply

class QuantumInspiredGraphEngine:
    """Experimental quantum-walk-inspired graph features; makes no claim that markets are quantum."""
    def __init__(self,enabled:bool=False,max_nodes:int=128,gamma:float=0.25) -> None:
        self.enabled=enabled; self.max_nodes=max_nodes; self.gamma=gamma

    def features(self,graph:nx.Graph,active_wallets:list[str],dt:float=1.0)->dict[str,float]:
        zero={'quantum_localization':0.0,'state_entropy':0.0,'cohort_coherence':0.0}
        if not self.enabled or len(active_wallets)<2: return zero
        nodes=list(dict.fromkeys(active_wallets))[:self.max_nodes]
        sub=graph.subgraph(nodes).copy()
        if sub.number_of_nodes()<2: return zero
        nodelist=list(sub.nodes())
        A=nx.to_scipy_sparse_array(sub,nodelist=nodelist,weight='confidence',dtype=float,format='csr')
        deg=np.asarray(A.sum(axis=1)).reshape(-1)
        H=csr_matrix(np.diag(deg))-A
        psi=np.zeros(len(nodelist),dtype=np.complex128)
        psi[0]=1.0
        out=expm_multiply((-1j*self.gamma*dt)*H,psi)
        p=np.abs(out)**2; p=p/max(p.sum(),1e-12)
        loc=float((p**2).sum())
        ent=float(-(p*np.log(p+1e-12)).sum()/max(np.log(len(p)),1e-12))
        coherence=float(abs(np.sum(out))/max(np.sqrt(len(out)),1e-12))
        return {'quantum_localization':loc,'state_entropy':ent,'cohort_coherence':coherence}
