from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from finance.idempotency import assess_probable_duplicate

WIB = ZoneInfo("Asia/Jakarta")
REF = datetime(2026, 11, 2, 8, 5, tzinfo=WIB)


def row(desc, amount=18000, cat="food_drink", when=None, rid="row-1"):
    return {
        "id": rid, "description": desc, "amount_idr": amount,
        "category_code": cat, "occurred_at": when or REF - timedelta(hours=1),
    }


def test_probable_duplicate_detected():
    cand = {"description": "Bakso", "amount_idr": 18000,
            "category_code": "food_drink"}
    verdict = assess_probable_duplicate(cand, [row("bakso")], REF)
    assert verdict is not None and verdict.expense_id == "row-1"


def test_same_amount_different_item_not_flagged():
    cand = {"description": "Parkir motor", "amount_idr": 18000,
            "category_code": "food_drink"}
    assert assess_probable_duplicate(cand, [row("bakso")], REF) is None


def test_outside_window_not_flagged():
    cand = {"description": "Bakso", "amount_idr": 18000,
            "category_code": "food_drink"}
    old = row("bakso", when=REF - timedelta(hours=30))
    assert assess_probable_duplicate(cand, [old], REF) is None
