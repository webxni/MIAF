"""Money helpers. All amounts are Decimal with 2 dp."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value: Decimal | int | str) -> Decimal:
    """Quantize to 2 decimal places using bankers-friendly half-up."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)
