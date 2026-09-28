from __future__ import annotations

import asyncio
import time
import httpx
from ..domain.events import MarketEvent

WSOL='So11111111111111111111111111111111111111112'
USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'


class DexScreenerEnricher:
    """Exact-mint market enrichment with cache, connection reuse and bounded retries."""

    def __init__(
        self,
        ttl_seconds: float = 2.0,
        sol_ttl_seconds: float = 10.0,
        timeout: float = 5.0,
        max_concurrency: int = 4,
        max_retries: int = 2,
    ):
        self.ttl=float(ttl_seconds)
        self.sol_ttl=float(sol_ttl_seconds)
        self.timeout=float(timeout)
        self.max_retries=max(0,int(max_retries))
        self.cache={}
        self.sol_cache=(0.0,None)
        self._client: httpx.AsyncClient | None = None
        self._sem=asyncio.Semaphore(max(1,int(max_concurrency)))

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client=httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client=None

    async def _get_json(self,url:str):
        async with self._sem:
            client=self._http()
            for attempt in range(self.max_retries+1):
                try:
                    r=await client.get(url)
                except httpx.RequestError:
                    if attempt>=self.max_retries:
                        raise
                    await asyncio.sleep(min(4.0,0.25*(2**attempt)))
                    continue
                retryable=r.status_code==429 or 500<=r.status_code<600
                if retryable and attempt<self.max_retries:
                    raw=r.headers.get('retry-after')
                    try: delay=float(raw) if raw is not None else 0.25*(2**attempt)
                    except (TypeError,ValueError): delay=0.25*(2**attempt)
                    await asyncio.sleep(max(0.1,min(4.0,delay)))
                    continue
                r.raise_for_status()
                return r.json()
        return None

    async def _pairs(self,mint:str):
        now=time.monotonic()
        cached=self.cache.get(mint)
        if cached and now-cached[0] <= self.ttl:
            return cached[1]

        # Recheck after entering the shared request budget to reduce same-mint stampedes.
        async with self._sem:
            now=time.monotonic()
            cached=self.cache.get(mint)
            if cached and now-cached[0] <= self.ttl:
                return cached[1]
            client=self._http()
            url=f'https://api.dexscreener.com/tokens/v1/solana/{mint}'
            data=None
            for attempt in range(self.max_retries+1):
                try:
                    r=await client.get(url)
                except httpx.RequestError:
                    if attempt>=self.max_retries:
                        raise
                    await asyncio.sleep(min(4.0,0.25*(2**attempt)))
                    continue
                retryable=r.status_code==429 or 500<=r.status_code<600
                if retryable and attempt<self.max_retries:
                    raw=r.headers.get('retry-after')
                    try: delay=float(raw) if raw is not None else 0.25*(2**attempt)
                    except (TypeError,ValueError): delay=0.25*(2**attempt)
                    await asyncio.sleep(max(0.1,min(4.0,delay)))
                    continue
                r.raise_for_status()
                data=r.json()
                break

        pairs=data if isinstance(data,list) else data.get('pairs',[]) if isinstance(data,dict) else []
        verified=[
            p for p in pairs
            if p.get('chainId')=='solana'
            and (p.get('baseToken') or {}).get('address')==mint
        ]
        self.cache[mint]=(time.monotonic(),verified)
        return verified

    async def _sol_usd(self):
        now=time.monotonic()
        if self.sol_cache[1] is not None and now-self.sol_cache[0] <= self.sol_ttl:
            return self.sol_cache[1]
        pairs=await self._pairs(WSOL)
        prices=[]
        for p in pairs:
            try:
                if p.get('priceUsd') is not None:
                    prices.append(float(p['priceUsd']))
            except (TypeError,ValueError):
                continue
        value=prices[0] if prices else None
        self.sol_cache=(time.monotonic(),value)
        return value

    async def enrich(self,e:MarketEvent)->MarketEvent:
        if not e.asset_match_verified:
            return e
        try:
            needs_market = (
                e.price_usd is None
                or e.liquidity_usd is None
                or e.market_cap_usd is None
                or not e.metadata.get('token_name')
                or not e.metadata.get('token_symbol')
                or not e.metadata.get('token_image_url')
            )
            if needs_market:
                pairs=await self._pairs(e.token_mint)
                if pairs:
                    def liq(p):
                        try:return float((p.get('liquidity') or {}).get('usd') or 0)
                        except (TypeError,ValueError):return 0.0
                    p=max(pairs,key=liq)
                    if (p.get('baseToken') or {}).get('address')==e.token_mint:
                        if p.get('priceUsd') is not None:
                            e.price_usd=float(p['priceUsd'])
                        e.liquidity_usd=liq(p)
                        mc=p.get('marketCap') if p.get('marketCap') is not None else p.get('fdv')
                        if mc is not None:
                            e.market_cap_usd=float(mc)
                        if p.get('pairCreatedAt') and e.token_age_seconds is None:
                            e.token_age_seconds=max(0.0,e.timestamp.timestamp()-float(p['pairCreatedAt'])/1000.0)
                        base = p.get('baseToken') or {}
                        info = p.get('info') or {}
                        if base.get('name'):
                            e.metadata['token_name'] = str(base['name'])
                        if base.get('symbol'):
                            e.metadata['token_symbol'] = str(base['symbol'])
                        if info.get('imageUrl'):
                            e.metadata['token_image_url'] = str(info['imageUrl'])
                        if p.get('url'):
                            e.metadata['dexscreener_url'] = str(p['url'])
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
