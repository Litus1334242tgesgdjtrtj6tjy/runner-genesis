from __future__ import annotations
import asyncio, json
from typing import AsyncIterator
import websockets

class SolanaLogSubscriber:
    """Low-level Solana logsSubscribe stream. Program-specific transaction decoding is intentionally separate."""
    def __init__(self,ws_url:str,mentions:list[str]|None=None): self.ws_url=ws_url; self.mentions=mentions or []

    async def messages(self)->AsyncIterator[dict]:
        async with websockets.connect(self.ws_url,ping_interval=20,ping_timeout=20) as ws:
            filt={'mentions':self.mentions} if self.mentions else 'all'
            req={'jsonrpc':'2.0','id':1,'method':'logsSubscribe','params':[filt,{'commitment':'confirmed'}]}
            await ws.send(json.dumps(req)); await ws.recv()
            async for raw in ws: yield json.loads(raw)
