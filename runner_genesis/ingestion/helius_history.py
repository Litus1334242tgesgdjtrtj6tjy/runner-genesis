from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import hashlib
from typing import Any

import httpx

from ..domain.events import EventType, MarketEvent
from ..domain.state import WalletBuyObservation


WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
QUOTE_MINTS = {WSOL, USDC, USDT}


@dataclass(frozen=True)
class FundingLink:
    wallet: str
    funder: str
    timestamp: datetime
    sol_amount: float | None
    signature: str | None
    confidence: float = 0.90


class HeliusWalletHistoryClient:
    """Read-only Helius Enhanced Transactions history client.

    This adapter is intentionally isolated from execution. It is used only for research
    backfill / wallet qualification. Helius API credentials are read from configuration
    and are never persisted by this class.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.helius.xyz",
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("HELIUS_API_KEY is required for wallet backfill")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = max(0, int(max_retries))

    async def fetch_transactions(
        self,
        address: str,
        *,
        limit: int = 100,
        max_pages: int = 5,
        before: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch newest-first Enhanced Transactions with conservative pagination."""
        address = str(address).strip()
        if not address:
            return []
        limit = max(1, min(int(limit), 100))
        pages = max(1, int(max_pages))
        cursor = before
        out: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for _ in range(pages):
                params: dict[str, Any] = {"api-key": self.api_key, "limit": limit}
                if cursor:
                    params["before"] = cursor
                url = f"{self.base_url}/v0/addresses/{address}/transactions"
                payload = None
                for attempt in range(self.max_retries + 1):
                    try:
                        response = await client.get(url, params=params)
                    except httpx.RequestError:
                        if attempt >= self.max_retries:
                            raise
                        await asyncio.sleep(min(8.0, 0.5 * (2 ** attempt)))
                        continue
                    retryable = response.status_code == 429 or 500 <= response.status_code < 600
                    if retryable and attempt < self.max_retries:
                        raw = response.headers.get("retry-after")
                        try:
                            delay = float(raw) if raw is not None else 0.5 * (2 ** attempt)
                        except (TypeError, ValueError):
                            delay = 0.5 * (2 ** attempt)
                        await asyncio.sleep(min(10.0, max(0.25, delay)))
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    break
                if not isinstance(payload, list) or not payload:
                    break
                rows = [x for x in payload if isinstance(x, dict)]
                for row in rows:
                    sig = str(row.get("signature") or "")
                    if sig and sig in seen_signatures:
                        continue
                    if sig:
                        seen_signatures.add(sig)
                    out.append(row)
                if len(rows) < limit:
                    break
                last_sig = rows[-1].get("signature")
                if not last_sig or last_sig == cursor:
                    break
                cursor = str(last_sig)
        return out


class EnhancedWalletHistoryNormalizer:
    """Convert Helius Enhanced Transactions into conservative wallet BUY/SELL events.

    A SWAP is classified only when exactly one non-quote token has a non-zero wallet
    delta and the wallet has a clear opposite quote delta (native SOL/WSOL/USDC/USDT).
    Ambiguous token-token swaps are ignored rather than guessed.
    """

    @staticmethod
    def _timestamp(tx: dict[str, Any]) -> datetime:
        raw = tx.get("timestamp") or tx.get("blockTime")
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _num(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _token_deltas(self, wallet: str, tx: dict[str, Any]) -> dict[str, float]:
        deltas: dict[str, float] = {}
        for tr in tx.get("tokenTransfers") or []:
            if not isinstance(tr, dict):
                continue
            mint = tr.get("mint") or tr.get("tokenMint")
            if not mint:
                continue
            amount = self._num(tr.get("tokenAmount") if tr.get("tokenAmount") is not None else tr.get("amount"))
            frm = tr.get("fromUserAccount") or tr.get("fromTokenAccount")
            to = tr.get("toUserAccount") or tr.get("toTokenAccount")
            delta = 0.0
            if to == wallet:
                delta += amount
            if frm == wallet:
                delta -= amount
            if delta:
                deltas[str(mint)] = deltas.get(str(mint), 0.0) + delta
        return deltas

    def _native_sol_delta(self, wallet: str, tx: dict[str, Any]) -> float:
        lamports = 0.0
        for tr in tx.get("nativeTransfers") or []:
            if not isinstance(tr, dict):
                continue
            amount = self._num(tr.get("amount"))
            frm = tr.get("fromUserAccount")
            to = tr.get("toUserAccount")
            if to == wallet:
                lamports += amount
            if frm == wallet:
                lamports -= amount
        return lamports / 1_000_000_000.0

    def normalize_swap(self, wallet: str, tx: dict[str, Any]) -> list[MarketEvent]:
        if str(tx.get("type") or "").upper() != "SWAP":
            return []
        token_deltas = self._token_deltas(wallet, tx)
        candidates = [(m, d) for m, d in token_deltas.items() if m not in QUOTE_MINTS and abs(d) > 1e-15]
        if len(candidates) != 1:
            return []
        mint, candidate_delta = candidates[0]

        sol_delta = self._native_sol_delta(wallet, tx)
        # WSOL transfers are folded into native SOL quote flow when present.
        sol_delta += token_deltas.get(WSOL, 0.0)
        usdc_delta = token_deltas.get(USDC, 0.0)
        usdt_delta = token_deltas.get(USDT, 0.0)

        quote_asset = None
        quote_delta = 0.0
        quote_unit = None
        if abs(sol_delta) > 1e-12:
            quote_asset, quote_delta, quote_unit = "SOL", sol_delta, "SOL"
        elif abs(usdc_delta) > 1e-12:
            quote_asset, quote_delta, quote_unit = "USDC", usdc_delta, "USD"
        elif abs(usdt_delta) > 1e-12:
            quote_asset, quote_delta, quote_unit = "USDT", usdt_delta, "USD"
        else:
            return []

        if candidate_delta > 0 and quote_delta < 0:
            event_type = EventType.BUY
        elif candidate_delta < 0 and quote_delta > 0:
            event_type = EventType.SELL
        else:
            return []

        ts = self._timestamp(tx)
        sig = str(tx.get("signature") or "")
        quote_value = abs(float(quote_delta))
        amount_token = abs(float(candidate_delta))
        usd_value = quote_value if quote_unit == "USD" else None
        price_usd = (usd_value / amount_token) if usd_value is not None and amount_token > 0 else None
        eid = hashlib.sha256(f"helius-history|{sig}|{wallet}|{mint}|{event_type.value}".encode()).hexdigest()[:24]
        return [MarketEvent(
            event_id=eid,
            timestamp=ts,
            tx_signature=sig or None,
            token_mint=mint,
            wallet=wallet,
            event_type=event_type,
            amount_token=amount_token,
            sol_value=quote_value if quote_asset == "SOL" else None,
            usd_value=usd_value,
            price_usd=price_usd,
            source="helius_enhanced_history",
            confidence=0.90,
            asset_match_verified=True,
            metadata={
                "quote_asset": quote_asset,
                "quote_value": quote_value,
                "history_backfill": True,
                "helius_type": tx.get("type"),
            },
        )]

    def funding_links(self, wallet: str, tx: dict[str, Any], min_sol: float = 0.01) -> list[FundingLink]:
        """Extract conservative direct incoming SOL funding evidence.

        Swap proceeds are NEVER funding evidence: treating a DEX pool that sends SOL on a
        SELL as a wallet funder would create giant false cohorts. We therefore only accept
        native-transfer-style transactions with no token transfer leg.
        """
        tx_type = str(tx.get("type") or "").upper()
        if tx_type == "SWAP" or (tx.get("tokenTransfers") or []):
            return []
        if tx_type and tx_type not in {"TRANSFER", "UNKNOWN"}:
            return []
        ts = self._timestamp(tx)
        sig = str(tx.get("signature") or "") or None
        out: list[FundingLink] = []
        for tr in tx.get("nativeTransfers") or []:
            if not isinstance(tr, dict):
                continue
            if tr.get("toUserAccount") != wallet:
                continue
            funder = tr.get("fromUserAccount")
            if not funder or funder == wallet:
                continue
            sol = self._num(tr.get("amount")) / 1_000_000_000.0
            if sol < float(min_sol):
                continue
            out.append(FundingLink(wallet=wallet, funder=str(funder), timestamp=ts, sol_amount=sol, signature=sig))
        return out


@dataclass
class _OpenCycle:
    token_mint: str
    quote_asset: str
    first_buy: datetime
    token_bought: float = 0.0
    token_sold: float = 0.0
    quote_spent: float = 0.0
    quote_received: float = 0.0

    @property
    def retained_fraction(self) -> float:
        if self.token_bought <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.token_bought - self.token_sold) / self.token_bought))


class WalletOutcomeBuilder:
    """Resolve closed wallet trade cycles without using data after the sell timestamp."""

    def build(self, events: list[MarketEvent]) -> list[WalletBuyObservation]:
        cycles: dict[str, _OpenCycle] = {}
        outcomes: list[WalletBuyObservation] = []
        for e in sorted(events, key=lambda x: x.timestamp):
            if e.event_type not in {EventType.BUY, EventType.SELL}:
                continue
            q_asset = str((e.metadata or {}).get("quote_asset") or "")
            q_value = self._quote_value(e)
            if not q_asset or q_value is None or q_value <= 0 or not e.amount_token:
                continue
            cycle = cycles.get(e.token_mint)
            if e.event_type == EventType.BUY:
                if cycle is None or cycle.retained_fraction <= 0.02:
                    cycle = _OpenCycle(e.token_mint, q_asset, e.timestamp)
                    cycles[e.token_mint] = cycle
                if cycle.quote_asset != q_asset:
                    # Mixed quote assets require external FX/SOL pricing. Do not guess.
                    cycles.pop(e.token_mint, None)
                    continue
                cycle.token_bought += float(e.amount_token)
                cycle.quote_spent += q_value
            else:
                if cycle is None or cycle.quote_asset != q_asset or cycle.token_bought <= 0:
                    continue
                sell_amount = max(0.0, float(e.amount_token))
                remaining = max(0.0, cycle.token_bought - cycle.token_sold)
                matched = min(sell_amount, remaining)
                if matched <= 0:
                    continue
                # A wallet can sell tokens it owned before the tracked cycle. Allocate
                # quote proceeds only to the quantity attributable to this cycle instead
                # of crediting the full oversized sale and manufacturing impossible ROI.
                allocation = matched / max(sell_amount, 1e-12)
                cycle.token_sold += matched
                cycle.quote_received += q_value * allocation
                if cycle.retained_fraction <= 0.02 and cycle.quote_spent > 0:
                    realized = cycle.quote_received / cycle.quote_spent - 1.0
                    outcomes.append(WalletBuyObservation(
                        event_time=cycle.first_buy,
                        resolved_at=e.timestamp,
                        token_mint=e.token_mint,
                        buy_eur=cycle.quote_spent if q_asset in {"USDC", "USDT"} else 0.0,
                        realized_return=realized,
                        runner_capture_ratio=None,
                        hold_seconds=max(0.0, (e.timestamp - cycle.first_buy).total_seconds()),
                    ))
                    cycles.pop(e.token_mint, None)
        return outcomes

    @staticmethod
    def _quote_value(e: MarketEvent) -> float | None:
        meta = e.metadata or {}
        q = meta.get("quote_value")
        if q is not None:
            try:
                return abs(float(q))
            except (TypeError, ValueError):
                return None
        if e.usd_value is not None:
            return abs(float(e.usd_value))
        if e.sol_value is not None:
            return abs(float(e.sol_value))
        return None
