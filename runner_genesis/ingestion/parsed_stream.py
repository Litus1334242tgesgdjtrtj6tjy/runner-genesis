from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import websockets


class HeliusParsedStreamSubscriber:
    """Helius Parsed Streams client using parsedTransactionSubscribe.

    The stream reconnects with bounded exponential backoff after transport failures.
    Server-side subscription/filter errors are surfaced immediately instead of silently
    retrying a bad configuration forever.
    """

    def __init__(
        self,
        api_key: str,
        programs: list[str],
        instruction_names: list[str] | None = None,
        include_cpi: bool = True,
        include_failed: bool = False,
        reconnect_min_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
    ):
        if not api_key:
            raise ValueError('HELIUS_API_KEY required')
        self.url = f'wss://fs-beta.helius-rpc.com/?api-key={api_key}'
        self.programs = programs
        self.instruction_names = instruction_names or []
        self.include_cpi = include_cpi
        self.include_failed = include_failed
        self.reconnect_min_seconds = max(0.1, float(reconnect_min_seconds))
        self.reconnect_max_seconds = max(self.reconnect_min_seconds, float(reconnect_max_seconds))

    def _request(self) -> dict:
        filt = {
            'programs': self.programs,
            'includeCpi': self.include_cpi,
            'includeFailed': self.include_failed,
        }
        if self.instruction_names:
            filt['instructionNames'] = self.instruction_names
        return {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'parsedTransactionSubscribe',
            'params': [filt],
        }

    async def payloads(self) -> AsyncIterator[dict]:
        delay = self.reconnect_min_seconds
        while True:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=16 * 1024 * 1024,
                ) as ws:
                    await ws.send(json.dumps(self._request()))
                    first = json.loads(await ws.recv())
                    if 'error' in first:
                        raise RuntimeError(f"Helius subscription error: {first['error']}")

                    # A successful subscription proves connectivity/configuration. Reset
                    # backoff so a later transient disconnect recovers quickly.
                    delay = self.reconnect_min_seconds
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        x = (msg.get('params') or {}).get('result', msg)
                        if isinstance(x, dict) and 'value' in x and isinstance(x['value'], dict):
                            x = x['value']
                        if isinstance(x, dict):
                            yield x
            except asyncio.CancelledError:
                raise
            except RuntimeError:
                # Authentication/filter/subscription errors need operator attention.
                raise
            except Exception:
                await asyncio.sleep(delay)
                delay = min(self.reconnect_max_seconds, delay * 2.0)
