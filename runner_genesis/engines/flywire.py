from __future__ import annotations
from pathlib import Path
import numpy as np
from scipy import sparse

class FlyWireReservoir:
    """Fixed sparse FAFB reservoir. Real topology is loaded from preprocessed user data."""
    def __init__(self,artifact_dir:str|Path,enabled:bool=False,state_dim:int=64,alpha:float=0.9,input_dim:int=16,seed:int=783,variant:str='FLY_REAL') -> None:
        self.enabled=enabled
        self.artifact_dir=Path(artifact_dir)
        self.alpha=float(alpha)
        self.input_dim=input_dim
        self._loaded=False
        self.state=None; self.W=None; self.B=None
        self.seed=seed
        self.variant=variant

    def _load(self):
        if self._loaded or not self.enabled: return
        files={'FLY_REAL':'adjacency.npz','FLY_SHUFFLED_WEIGHTS':'fly_shuffled_weights.npz','FLY_REWIRED':'fly_rewired.npz','FLY_DEGREE_PRESERVED':'fly_degree_preserved.npz','RANDOM_RESERVOIR':'random_reservoir.npz'}
        wpath=self.artifact_dir/files.get(self.variant,'adjacency.npz')
        if not wpath.exists():
            self.enabled=False; return
        self.W=sparse.load_npz(wpath).tocsr().astype(np.float32)
        n=self.W.shape[0]
        rowsum=np.asarray(np.abs(self.W).sum(axis=1)).reshape(-1)
        scale=max(float(rowsum.max()) if len(rowsum) else 1.0,1.0)
        self.W=self.W/scale
        rng=np.random.default_rng(self.seed)
        self.B=rng.normal(0,0.15,(n,self.input_dim)).astype(np.float32)
        self.state=np.zeros(n,dtype=np.float32)
        self._loaded=True

    def step(self,z:np.ndarray)->dict[str,float]:
        zero={'fly_state_mean':0.0,'fly_state_std':0.0,'fly_state_change':0.0,'fly_anomaly':0.0}
        if not self.enabled: return zero
        self._load()
        if not self.enabled or self.W is None: return zero
        z=np.asarray(z,dtype=np.float32).reshape(-1)[:self.input_dim]
        if len(z)<self.input_dim: z=np.pad(z,(0,self.input_dim-len(z)))
        prev=self.state.copy()
        recurrent=self.W.dot(self.state)
        inp=self.B.dot(z)
        self.state=np.tanh(self.alpha*recurrent+inp).astype(np.float32)
        delta=self.state-prev
        return {'fly_state_mean':float(self.state.mean()),'fly_state_std':float(self.state.std()),'fly_state_change':float(np.linalg.norm(delta)/max(np.sqrt(len(delta)),1)),'fly_anomaly':float(np.max(np.abs(delta)))}
