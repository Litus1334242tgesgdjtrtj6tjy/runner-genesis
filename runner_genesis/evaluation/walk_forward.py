from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator
import pandas as pd

@dataclass
class Fold:
    train_idx:list[int]; test_idx:list[int]

def expanding_walk_forward(df:pd.DataFrame,time_col:str,initial_train:int,test_size:int)->Iterator[Fold]:
    ordered=df.sort_values(time_col).reset_index()
    n=len(ordered); end=initial_train
    while end<n:
        test_end=min(n,end+test_size)
        yield Fold(ordered.iloc[:end]['index'].tolist(),ordered.iloc[end:test_end]['index'].tolist())
        end=test_end
