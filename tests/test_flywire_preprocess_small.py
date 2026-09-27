import pandas as pd
from scipy import sparse
from runner_genesis.flywire.preprocess import preprocess_connections

def test_flywire_preprocess(tmp_path):
    p=tmp_path/'c.csv.gz'
    pd.DataFrame({'pre_root_id':[1,1,2,3],'post_root_id':[2,3,3,1],'syn_count':[4,1,5,2]}).to_csv(p,index=False,compression='gzip')
    meta=preprocess_connections(p,tmp_path/'out',max_nodes=3,min_syn_count=2,chunksize=2)
    W=sparse.load_npz(tmp_path/'out'/'adjacency.npz')
    assert W.shape==(3,3)
    assert meta['edge_count']==3
