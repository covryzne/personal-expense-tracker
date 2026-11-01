"""IDR money helpers. Amounts are integer rupiah everywhere (no floats
cross the boundary; parsing accepts Indonesian shorthand deterministically).
"""
from __future__ import annotations

import re

_PLAIN = re.compile(r"^\d+$")
_GROUPED = re.compile(r"^\d{1,3}(\.\d{3})+$")
_SUFFIX = re.compile(
    r"^(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>rb|ribu|k|jt|juta)$", re.IGNORECASE
)


def format_idr(amount: int) -> str:
    """12000 -> 'Rp12.000' (TOOL_CONTRACT §9)."""
    if amount < 0:
        raise ValueError("amount must be >= 0")
    return "Rp" + f"{amount:,}".replace(",", ".")


def parse_amount_idr(text: str) -> int | None:
    """Parse an Indonesian amount expression to integer IDR, or None.

    Accepts: '12000', '12.000', 'Rp12.000', '12rb', '12 ribu', '15k',
    '1,5jt', '2 juta'. Returns None for anything ambiguous or invalid.
    """
    if text is None:
        return None
    s = str(text).strip()
    s = re.sub(r"^rp\.?\s*", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return None
    if _PLAIN.match(s):
        return int(s)
    if _GROUPED.match(s):
        return int(s.replace(".", ""))
    m = _SUFFIX.match(s)
    if m:
        num = m.group("num").replace(".", "").replace(",", ".")
        try:
            value = float(num)
        except ValueError:
            return None
        unit = m.group("unit").lower()
        mult = 1_000 if unit in ("rb", "ribu", "k") else 1_000_000
        result = value * mult
        if result != int(result) or result <= 0:
            return None
        return int(result)
    return None
