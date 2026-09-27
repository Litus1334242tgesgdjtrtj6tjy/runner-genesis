from __future__ import annotations
import time
import httpx
from ..domain.events import MarketEvent

WSOL='So11111111111111111111111111111111111111112'
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'

class DexScreenerEnricher:
    """Mint-verified market enrichment using DEX Screener token endpoint.

    Pair selection is restricted to Solana and requires the supplied mint to be the base token.
    Symbol/name is never used for identity.
    """
    def __init__(self,ttl_seconds:float=2.0,sol_ttl_seconds:float=10.0,timeout:float=5.0):
        self.ttl=ttl_seconds; self.sol_ttl=sol_ttl_seconds; self.timeout=timeout
        self.cache={}; self.sol_cache=(0.0,None)

    async def _pairs(self,mint:str):
        now=time.monotonic()
        if mint in self.cache and now-self.cache[mint][0] <= self.ttl:
            return self.cache[mint][1]
        url=f'https://api.dexscreener.com/tokens/v1/solana/{mint}'
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r=await c.get(url); r.raise_for_status(); data=r.json()
        pairs=data if isinstance(data,list) else data.get('pairs',[]) if isinstance(data,dict) else []
        verified=[p for p in pairs if p.get('chainId')=='solana' and (p.get('baseToken') or {}).get('address')==mint]
        self.cache[mint]=(now,verified)
        return verified

    async def _sol_usd(self):
        now=time.monotonic()
        if self.sol_cache[1] is not None and now-self.sol_cache[0] <= self.sol_ttl:
            return self.sol_cache[1]
        pairs=await self._pairs(WSOL)
        prices=[float(p['priceUsd']) for p in pairs if p.get('priceUsd')]
        value=float(prices[0]) if prices else None
        self.sol_cache=(now,value)
        return value

    async def enrich(self,e:MarketEvent)->MarketEvent:
        if not e.asset_match_verified: return e
        try:
            pairs=await self._pairs(e.token_mint)
            if pairs:
                def liq(p):
                    try:return float((p.get('liquidity') or {}).get('usd') or 0)
                    except:return 0.0
                p=max(pairs,key=liq)
                if (p.get('baseToken') or {}).get('address')==e.token_mint:
                    if p.get('priceUsd') is not None: e.price_usd=float(p['priceUsd'])
                    e.liquidity_usd=liq(p)
                    mc=p.get('marketCap') if p.get('marketCap') is not None else p.get('fdv')
                    if mc is not None: e.market_cap_usd=float(mc)
                    if p.get('pairCreatedAt') and e.token_age_seconds is None:
                        e.token_age_seconds=max(0.0,e.timestamp.timestamp()-float(p['pairCreatedAt'])/1000.0)
                    e.metadata['dexscreener_pair']=p.get('pairAddress')
                    e.metadata['dexscreener_dex']=p.get('dexId')
            if e.sol_value is not None:
                sol=await self._sol_usd()
                if sol is not None:
                    e.metadata['sol_usd']=float(sol)
                    if e.usd_value is None:
                        e.usd_value=float(e.sol_value)*float(sol)
        except Exception as ex:
            e.metadata['market_enrichment_error']=type(ex).__name__
        return e
