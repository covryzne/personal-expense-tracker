"""Layer-2 duplicate assessment (docs/ADAPTER.md): used only when the
idempotency key is a derived command key (post-clarification writes),
where the exact-key unique constraint cannot recognize a re-send.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher

WINDOW = timedelta(hours=24)
DESCRIPTION_SIMILARITY = 0.85


@dataclass(frozen=True)
class ProbableDuplicate:
    expense_id: str
    reason: str


def assess_probable_duplicate(
    candidate: dict,
    recent_rows: list[dict],
    reference_time: datetime,
) -> ProbableDuplicate | None:
    """Return a probable-duplicate verdict or None.

    candidate/recent rows use expense field names (amount_idr,
    category_code, description, occurred_at as aware datetime,
    id for rows).
    """
    window_start = reference_time - WINDOW
    for row in recent_rows:
        occurred = row.get("occurred_at")
        if occurred is None or not (window_start <= occurred <= reference_time):
            continue
        if row.get("amount_idr") != candidate.get("amount_idr"):
            continue
        if row.get("category_code") != candidate.get("category_code"):
            continue
        ratio = SequenceMatcher(
            None,
            (row.get("description") or "").strip().lower(),
            (candidate.get("description") or "").strip().lower(),
        ).ratio()
        if ratio >= DESCRIPTION_SIMILARITY:
            return ProbableDuplicate(
                expense_id=str(row.get("id")),
                reason=(
                    f"same amount+category within 24h, description "
                    f"similarity {ratio:.2f}"
                ),
            )
    return None
