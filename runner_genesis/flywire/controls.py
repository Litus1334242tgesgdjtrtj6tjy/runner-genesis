from __future__ import annotations
from pathlib import Path
import json
import numpy as np
from scipy import sparse


def _coo(W):
    C=W.tocoo()
    return C.row.astype(np.int32),C.col.astype(np.int32),C.data.astype(np.float32)


def shuffled_weights(W,seed=783):
    r,c,w=_coo(W); rng=np.random.default_rng(seed); ww=w.copy(); rng.shuffle(ww)
    return sparse.coo_matrix((ww,(r,c)),shape=W.shape).tocsr()


def rewired_destinations(W,seed=784):
    """Null topology: same edge sources and weight multiset, shuffled destinations.
    Duplicate edges are collapsed, so exact node degrees can change slightly after collapse.
    """
    r,c,w=_coo(W); rng=np.random.default_rng(seed); cc=c.copy(); rng.shuffle(cc)
    X=sparse.coo_matrix((w,(r,cc)),shape=W.shape).tocsr(); X.sum_duplicates(); return X


def degree_sequence_stub_control(W,seed=785):
    """Directed stub-pair null approximately preserving in/out degree sequences.
    Multi-edge collapse can create small deviations; metadata reports them.
    """
    r,c,w=_coo(W); rng=np.random.default_rng(seed); cc=c.copy(); rng.shuffle(cc); ww=w.copy(); rng.shuffle(ww)
    X=sparse.coo_matrix((ww,(r,cc)),shape=W.shape).tocsr(); X.sum_duplicates(); return X


def random_reservoir_like(W,seed=786):
    r,c,w=_coo(W); rng=np.random.default_rng(seed); n=W.shape[0]; nnz=len(w)
    rr=rng.integers(0,n,size=nnz,dtype=np.int32); cc=rng.integers(0,n,size=nnz,dtype=np.int32)
    ww=rng.choice(w,size=nnz,replace=True)
    X=sparse.coo_matrix((ww,(rr,cc)),shape=W.shape).tocsr(); X.sum_duplicates(); return X


def generate_controls(artifact_dir:str|Path,seed:int=783):
    d=Path(artifact_dir); W=sparse.load_npz(d/'adjacency.npz').tocsr()
    variants={
      'FLY_SHUFFLED_WEIGHTS':shuffled_weights(W,seed+1),
      'FLY_REWIRED':rewired_destinations(W,seed+2),
      'FLY_DEGREE_PRESERVED':degree_sequence_stub_control(W,seed+3),
      'RANDOM_RESERVOIR':random_reservoir_like(W,seed+4),
    }
    meta={}
    out_deg=np.diff(W.indptr); in_deg=np.bincount(W.indices,minlength=W.shape[0])
    for name,X in variants.items():
        path=d/(name.lower()+'.npz'); sparse.save_npz(path,X,compressed=True)
        xo=np.diff(X.indptr); xi=np.bincount(X.indices,minlength=X.shape[0])
        meta[name]={
          'path':path.name,'nodes':int(X.shape[0]),'edges':int(X.nnz),'weight_sum':float(X.sum()),
          'mean_abs_out_degree_delta':float(np.mean(np.abs(xo-out_deg))),
          'mean_abs_in_degree_delta':float(np.mean(np.abs(xi-in_deg))),
          'seed':seed,
        }
    (d/'controls_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta
