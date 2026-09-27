from __future__ import annotations
import json
from typing import AsyncIterator
import websockets

class HeliusParsedStreamSubscriber:
    """Current Helius Parsed Streams client using parsedTransactionSubscribe."""
    def __init__(self,api_key:str,programs:list[str],instruction_names:list[str]|None=None,include_cpi:bool=True,include_failed:bool=False):
        if not api_key: raise ValueError('HELIUS_API_KEY required')
        self.url=f'wss://fs-beta.helius-rpc.com/?api-key={api_key}'
        self.programs=programs; self.instruction_names=instruction_names or []
        self.include_cpi=include_cpi; self.include_failed=include_failed

    async def payloads(self)->AsyncIterator[dict]:
        filt={'programs':self.programs,'includeCpi':self.include_cpi,'includeFailed':self.include_failed}
        if self.instruction_names: filt['instructionNames']=self.instruction_names
        req={'jsonrpc':'2.0','id':1,'method':'parsedTransactionSubscribe','params':[filt]}
        async with websockets.connect(self.url,ping_interval=20,ping_timeout=20,max_size=16*1024*1024) as ws:
            await ws.send(json.dumps(req)); first=json.loads(await ws.recv())
            if 'error' in first: raise RuntimeError(f"Helius subscription error: {first['error']}")
            async for raw in ws:
                msg=json.loads(raw)
                x=(msg.get('params') or {}).get('result',msg)
                if isinstance(x,dict) and 'value' in x and isinstance(x['value'],dict): x=x['value']
                if isinstance(x,dict): yield x
