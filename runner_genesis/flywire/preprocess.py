from __future__ import annotations
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
from scipy import sparse

REQUIRED_COLUMNS={'pre_root_id','post_root_id','syn_count'}

def sha256(path:Path,chunk=1024*1024)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b=f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def preprocess_connections(input_csv_gz:str|Path,out_dir:str|Path,max_nodes:int|None=20000,min_syn_count:int=2,chunksize:int=1_000_000)->dict:
    inp=Path(input_csv_gz); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    # Pass 1: weighted degree to choose a manageable production reservoir.
    degree={}
    rows=0
    for ch in pd.read_csv(inp,usecols=['pre_root_id','post_root_id','syn_count'],chunksize=chunksize):
        ch=ch[ch.syn_count>=min_syn_count]; rows+=len(ch)
        for col in ('pre_root_id','post_root_id'):
            sums=ch.groupby(col,sort=False).syn_count.sum()
            for rid,val in sums.items(): degree[int(rid)]=degree.get(int(rid),0.0)+float(val)
    ids=np.array(sorted(degree,key=degree.get,reverse=True)[:max_nodes] if max_nodes else sorted(degree),dtype=np.int64)
    idx={int(r):i for i,r in enumerate(ids)}
    rr=[]; cc=[]; vv=[]; kept=0
    for ch in pd.read_csv(inp,usecols=['pre_root_id','post_root_id','syn_count'],chunksize=chunksize):
        ch=ch[ch.syn_count>=min_syn_count]
        mask=ch.pre_root_id.isin(idx) & ch.post_root_id.isin(idx); ch=ch[mask]
        if ch.empty: continue
        rr.extend(ch.pre_root_id.map(idx).astype(np.int32).tolist()); cc.extend(ch.post_root_id.map(idx).astype(np.int32).tolist()); vv.extend(ch.syn_count.astype(np.float32).tolist()); kept+=len(ch)
    W=sparse.coo_matrix((np.asarray(vv,dtype=np.float32),(np.asarray(rr,dtype=np.int32),np.asarray(cc,dtype=np.int32))),shape=(len(ids),len(ids))).tocsr()
    W.sum_duplicates(); sparse.save_npz(out/'adjacency.npz',W,compressed=True); np.save(out/'root_ids.npy',ids)
    meta={'source':inp.name,'source_sha256':sha256(inp),'connectome_version':'FAFB/FlyWire public release 783','min_syn_count':min_syn_count,'max_nodes':max_nodes,'node_count':int(W.shape[0]),'edge_count':int(W.nnz),'input_rows_after_threshold':rows,'kept_rows_before_collapse':kept,'weight_sum':float(W.sum()),'preprocessing':'top weighted-degree induced subgraph'}
    (out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta
