from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FeeQuote:
    protocol_fee_bps: float | None
    source: str
    schedule_version: str
    confidence: float
    reason: str


class PumpFeeSchedule:
    """Pump.fun/PumpSwap trading-fee schedule for research simulation.

    Schedule source: pump.fun/docs/fees, last-updated 2026-05-20 and effective
    2026-05-21 for the SOL/USDC schedules described there.

    The implementation is deliberately conservative when canonical-pool or SOL/USD
    information is missing. Fees are execution costs, not alpha features.
    """

    VERSION = "PUMP_FEES_2026-05-21"

    # Upper bound is exclusive except the final infinity bucket.
    SOL_CANONICAL = (
        (420, 125.0), (1470, 120.0), (2460, 115.0), (3440, 110.0),
        (4420, 105.0), (9820, 100.0), (14740, 95.0), (19650, 90.0),
        (24560, 85.0), (29470, 80.0), (34380, 75.0), (39300, 70.0),
        (44210, 65.0), (49120, 60.0), (54030, 55.0), (58940, 52.5),
        (63860, 50.0), (68770, 47.5), (73681, 45.0), (78590, 42.5),
        (83500, 40.0), (88400, 37.5), (93330, 35.0), (98240, 32.5),
        (float("inf"), 30.0),
    )

    USDC_CANONICAL = (
        (59_000, 125.0), (100_000, 120.0), (200_000, 120.0),
        (300_000, 120.0), (400_000, 115.0), (500_000, 115.0),
        (600_000, 110.0), (700_000, 110.0), (800_000, 105.0),
        (900_000, 105.0), (1_000_000, 100.0), (2_000_000, 100.0),
        (3_000_000, 95.0), (4_000_000, 90.0), (5_000_000, 85.0),
        (6_000_000, 80.0), (7_000_000, 75.0), (8_000_000, 70.0),
        (9_000_000, 65.0), (10_000_000, 60.0), (11_000_000, 55.0),
        (12_000_000, 53.0), (13_000_000, 50.0), (14_000_000, 48.0),
        (15_000_000, 45.0), (16_000_000, 43.0), (17_000_000, 40.0),
        (18_000_000, 38.0), (19_000_000, 35.0), (20_000_000, 33.0),
        (float("inf"), 30.0),
    )

    @staticmethod
    def _bucket(value: float, schedule) -> float:
        value = max(0.0, float(value))
        for upper, bps in schedule:
            if value < upper:
                return float(bps)
        return float(schedule[-1][1])

    @staticmethod
    def _pump_context(metadata: dict[str, Any]) -> bool:
        text = " ".join(
            str(metadata.get(k) or "")
            for k in ("launchpad", "protocol", "dexscreener_dex", "program", "program_id")
        ).lower()
        return "pump" in text

    def quote(self, token) -> FeeQuote:
        meta = dict(getattr(token, "metadata", {}) or {})
        if not self._pump_context(meta):
            return FeeQuote(None, "UNKNOWN_OR_NON_PUMP", self.VERSION, 0.0, "NO_EXPLICIT_PUMP_CONTEXT")

        # Bonding-curve trades are 1.25% for SOL and USDC. Migration evidence marks the
        # transition away from the bonding curve; if no migration/pool evidence exists,
        # this is the conservative Pump default.
        migrated = getattr(token, "migration_at", None) is not None
        pool_kind = str(meta.get("pool_kind") or "").upper()
        canonical = meta.get("pump_pool_canonical")
        if not migrated and "PUMPSWAP" not in str(meta.get("protocol") or "").upper():
            return FeeQuote(125.0, "PUMP_BONDING_CURVE", self.VERSION, 0.95, "BONDING_CURVE_TOTAL_FEE")

        if canonical is False or pool_kind == "NON_CANONICAL":
            return FeeQuote(30.0, "PUMPSWAP_NON_CANONICAL", self.VERSION, 0.90, "NON_CANONICAL_TOTAL_FEE")

        quote_asset = str(meta.get("quote_asset") or "").upper()
        market_cap_usd = getattr(token, "market_cap_usd", None)
        if quote_asset == "USDC" and market_cap_usd is not None:
            bps = self._bucket(float(market_cap_usd), self.USDC_CANONICAL)
            return FeeQuote(bps, "PUMPSWAP_CANONICAL_USDC", self.VERSION, 0.90, "USDC_MARKET_CAP_TIER")

        if quote_asset == "SOL" and market_cap_usd is not None:
            sol_usd = meta.get("sol_usd")
            try:
                sol_usd = float(sol_usd) if sol_usd is not None else None
            except (TypeError, ValueError):
                sol_usd = None
            if sol_usd and sol_usd > 0:
                market_cap_sol = float(market_cap_usd) / sol_usd
                bps = self._bucket(market_cap_sol, self.SOL_CANONICAL)
                return FeeQuote(bps, "PUMPSWAP_CANONICAL_SOL", self.VERSION, 0.90, "SOL_MARKET_CAP_TIER")

        # Unknown quote/canonical detail: 1.25% is the highest current Pump schedule tier,
        # so PAPER does not get an unrealistically cheap fill.
        return FeeQuote(125.0, "PUMP_CONSERVATIVE_FALLBACK", self.VERSION, 0.55, "INSUFFICIENT_TIER_DATA")
