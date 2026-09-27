from __future__ import annotations
from dataclasses import dataclass
from ..domain.events import MarketEvent


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


class CandidateUniverseGate:
    """Conservative mint-address candidate gate.

    It only excludes exact known quote/native/system identifiers; it never infers identity
    from ticker symbols.
    """

    WSOL = 'So11111111111111111111111111111111111111112'
    USDC = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
    USDT = 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'
    SYSTEM_PROGRAM = '11111111111111111111111111111111'
    TOKEN_PROGRAM = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'

    def __init__(self, extra_blocked_mints: set[str] | None = None) -> None:
        self.blocked = {self.WSOL, self.USDC, self.USDT, self.SYSTEM_PROGRAM, self.TOKEN_PROGRAM, 'SOL'}
        self.blocked.update(extra_blocked_mints or set())

    def evaluate(self, event: MarketEvent) -> GateDecision:
        if not event.token_mint:
            return GateDecision(False, 'MISSING_MINT')
        if event.token_mint in self.blocked:
            return GateDecision(False, 'QUOTE_NATIVE_OR_SYSTEM_ASSET')
        return GateDecision(True, 'CANDIDATE')
