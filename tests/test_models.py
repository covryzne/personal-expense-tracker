from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from finance.models import CreateExpensesRequest, ExpenseCandidate

WIB = ZoneInfo("Asia/Jakarta")


def cand(**kw):
    base = dict(
        source_item_index=0, amount_idr=12000, category_code="food_drink",
        description="Matcha Coffee", occurred_at=datetime(
            2026, 10, 30, 12, 51, tzinfo=WIB),
    )
    base.update(kw)
    return ExpenseCandidate(**base)


def test_candidate_ok():
    assert cand().amount_idr == 12000


def test_candidate_rejects_user_id_injection():
    with pytest.raises(ValidationError):
        cand(user_id="11111111-2222-3333-4444-555555555555")


def test_candidate_rejects_bad_category_and_amount():
    with pytest.raises(ValidationError):
        cand(category_code="crypto")
    with pytest.raises(ValidationError):  # T26
        cand(amount_idr=0)
    with pytest.raises(ValidationError):
        cand(amount_idr=-100)


def test_request_rejects_duplicate_indexes():
    with pytest.raises(ValidationError):
        CreateExpensesRequest(
            source_message_id="m1",
            expenses=[cand(), cand()],
        )
