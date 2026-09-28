from __future__ import annotations
import csv, json
from pathlib import Path
from datetime import datetime
from typing import Iterator
from ..domain.events import MarketEvent

class ReplaySource:
    def __init__(self,path:str|Path): self.path=Path(path)

    def events(self)->Iterator[MarketEvent]:
        if self.path.suffix.lower()=='.jsonl':
            with self.path.open('r',encoding='utf-8') as f:
                for line in f:
                    if line.strip(): yield MarketEvent.model_validate_json(line)
        elif self.path.suffix.lower()=='.csv':
            with self.path.open('r',encoding='utf-8',newline='') as f:
                for row in csv.DictReader(f):
                    meta=json.loads(row.pop('metadata','{}') or '{}')
                    row['metadata']=meta
                    for k in ('slot','amount_token','sol_value','usd_value','price_usd','market_cap_usd','liquidity_usd','token_age_seconds','confidence'):
                        if k in row and row[k]=='': row[k]=None
                    if 'asset_match_verified' in row: row['asset_match_verified']=str(row['asset_match_verified']).lower() in ('1','true','yes')
                    yield MarketEvent.model_validate(row)
        else:
            raise ValueError('Replay supports .jsonl or .csv')
