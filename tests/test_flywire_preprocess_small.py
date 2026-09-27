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


def test_flywire_state_is_isolated_per_token(tmp_path):
    import numpy as np
    from scipy import sparse
    from runner_genesis.engines.flywire import FlyWireReservoir

    W = sparse.csr_matrix(np.array([
        [0.0, 1.0, 0.0],
        [0.5, 0.0, 0.5],
        [0.0, 1.0, 0.0],
    ], dtype=np.float32))
    sparse.save_npz(tmp_path / 'adjacency.npz', W)

    r = FlyWireReservoir(tmp_path, enabled=True, input_dim=2, seed=783)
    z = np.array([0.4, -0.2], dtype=np.float32)

    a1 = r.step(z, key='TOKEN_A')
    a2 = r.step(z, key='TOKEN_A')
    b1 = r.step(z, key='TOKEN_B')

    assert a1['fly_status'] == 'ACTIVE'
    assert b1['fly_status'] == 'ACTIVE'
    assert abs(a1['fly_state_mean'] - b1['fly_state_mean']) < 1e-12
    assert abs(a1['fly_state_change'] - b1['fly_state_change']) < 1e-12
    assert abs(a2['fly_state_mean'] - a1['fly_state_mean']) > 1e-8
    assert set(r.states) == {'TOKEN_A', 'TOKEN_B'}
