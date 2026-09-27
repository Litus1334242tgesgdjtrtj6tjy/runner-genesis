from __future__ import annotations

import json
import os

import httpx

from .config import Settings
from .ingestion.parsed_stream import HeliusParsedStreamSubscriber
from .ingestion.helius import HeliusOnChainNormalizer
from .ingestion.enrich import DexScreenerEnricher

PUMP_PROGRAM = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
PUMPSWAP_PROGRAM = 'pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA'


async def _post_event(client: httpx.AsyncClient, api_url: str, event) -> dict:
    """Send a normalized point-in-time event to the single PAPER engine owned by the API.

    Keeping the portfolio/decision engine in one process is intentional: the dashboard,
    risk governor and paper ledger must all observe the same state.
    """
    r = await client.post(
        f"{api_url.rstrip('/')}/api/event",
        json=event.model_dump(mode='json'),
    )
    r.raise_for_status()
    return r.json()


async def run_shadow(settings: Settings, programs: list[str] | None = None):
    if settings.live_trading:
        raise RuntimeError('Shadow runner refuses to start with live_trading=true')

    api_key = settings.helius_api_key or os.getenv('HELIUS_API_KEY')
    if not api_key:
        raise RuntimeError('HELIUS_API_KEY is empty. Put it in the project .env file.')

    api_url = os.getenv('RUNNER_API_URL', 'http://127.0.0.1:8000')
    sub = HeliusParsedStreamSubscriber(api_key, programs or [PUMP_PROGRAM, PUMPSWAP_PROGRAM])
    norm = HeliusOnChainNormalizer()
    enrich = DexScreenerEnricher()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fail early with a useful message if RUN_PAPER is not running.
            try:
                health = await client.get(f"{api_url.rstrip('/')}/health")
                health.raise_for_status()
            except Exception as exc:
                raise RuntimeError(
                    f'RUN_PAPER/API is not reachable at {api_url}. Start scripts\\RUN_PAPER.bat first.'
                ) from exc

            print(json.dumps({
                'status': 'shadow_connected_to_paper_api',
                'api_url': api_url,
                'live_trading': False,
                'programs': programs or [PUMP_PROGRAM, PUMPSWAP_PROGRAM],
            }), flush=True)

            async for payload in sub.payloads():
                for event in norm.normalize(payload):
                    event = await enrich.enrich(event)
                    try:
                        result = await _post_event(client, api_url, event)
                    except Exception as exc:
                        print(json.dumps({
                            'status': 'paper_api_post_error',
                            'error': type(exc).__name__,
                            'mint': event.token_mint,
                        }), flush=True)
                        continue

                    snapshot = result.get('snapshot') or {}
                    probs = snapshot.get('probabilities') or {}
                    features = snapshot.get('features') or {}
                    fill = result.get('fill')
                    print(json.dumps({
                        'time': event.timestamp.isoformat(),
                        'mint': event.token_mint,
                        'event': event.event_type.value,
                        'action': snapshot.get('action'),
                        'genesis': probs.get('genesis_prob'),
                        'edge': features.get('expected_executable_edge'),
                        'risk_reasons': result.get('risk_reasons') or [],
                        'paper_fill': fill,
                    }, separators=(',', ':')), flush=True)
    finally:
        await enrich.aclose()

