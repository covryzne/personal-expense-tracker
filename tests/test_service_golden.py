"""Golden fixtures E1-E4 from TEST_PLAN §2, driven through the service
layer against an in-memory repository (unit level; the live Supabase
path is covered by the integration test once migrations are applied).
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from conftest import make_envelope
from fake_repo import FakeRepository
from finance import service
from finance.models import (
    CreateExpensesRequest, ExpenseCandidate, ExpensePatch, ReportRequest,
)

WIB = ZoneInfo("Asia/Jakarta")

FIXTURES = [
    # key, message_id, occurred WIB, amount, category, source_type, desc
    ("E1", "wa-e1", datetime(2026, 10, 30, 12, 51, tzinfo=WIB), 12000,
     "food_drink", "receipt", "Matcha Coffee Original"),
    ("E2", "wa-e2", datetime(2026, 10, 31, 22, 30, tzinfo=WIB), 50000,
     "transport", "voice", "Bensin"),
    ("E3", "wa-e3", datetime(2026, 11, 1, 0, 15, tzinfo=WIB), 2000,
     "transport", "text", "Parkir"),
    ("E4", "wa-e4", datetime(2026, 11, 2, 8, 0, tzinfo=WIB), 18000,
     "food_drink", "text", "Bakso"),
]


@pytest.fixture()
def seeded(settings):
    repo = FakeRepository()
    ids = {}
    for key, mid, when, amount, cat, stype, desc in FIXTURES:
        env = make_envelope(message_id=mid, sent_at=when, source_type=stype)
        req = CreateExpensesRequest(
            source_message_id=mid,
            expenses=[ExpenseCandidate(
                source_item_index=0, amount_idr=amount, category_code=cat,
                description=desc, occurred_at=when,
                timestamp_basis="receipt" if stype == "receipt"
                else "message_time",
                receipt_reference="NE/20261030/0045" if key == "E1" else None,
                merchant="Nescafe" if key == "E1" else None,
                payment_method="cash" if key == "E1" else "unknown",
            )],
        )
        res = service.create_expenses(settings, repo, env, req)
        assert res["status"] == "created", res
        ids[key] = res["data"]["expenses"][0]["id"]
    return repo, ids


def report(settings, repo, start, end):
    env = make_envelope(message_id="wa-report")
    res = service.get_report(settings, repo, env, ReportRequest(
        period="custom", start_date=start, end_date=end))
    assert res["ok"], res
    return res["data"]


def test_golden_month_totals(settings, seeded):
    repo, _ = seeded
    october = report(settings, repo, date(2026, 10, 1), date(2026, 10, 31))
    assert october["total_idr"] == 62000
    assert october["transaction_count"] == 2
    cats = {b["category_code"]: b["amount_idr"]
            for b in october["by_category"]}
    assert cats == {"food_drink": 12000, "transport": 50000}
    november = report(settings, repo, date(2026, 11, 1), date(2026, 11, 30))
    assert november["total_idr"] == 20000
    assert november["transaction_count"] == 2


def test_replay_same_message_is_already_recorded(settings, seeded):
    repo, _ = seeded
    key, mid, when, amount, cat, stype, desc = FIXTURES[0]
    env = make_envelope(message_id=mid, sent_at=when, source_type=stype)
    req = CreateExpensesRequest(
        source_message_id=mid,
        expenses=[ExpenseCandidate(
            source_item_index=0, amount_idr=amount, category_code=cat,
            description=desc, occurred_at=when, timestamp_basis="receipt")],
    )
    res = service.create_expenses(settings, repo, env, req)
    assert res["status"] == "already_recorded"  # T07
    october = report(settings, repo, date(2026, 10, 1), date(2026, 10, 31))
    assert october["transaction_count"] == 2


def test_delete_restore_cycle(settings, seeded):
    repo, ids = seeded
    env = make_envelope(message_id="wa-del")
    res = service.delete_expense(settings, repo, env, ids["E4"])
    assert res["status"] == "deleted"
    november = report(settings, repo, date(2026, 11, 1), date(2026, 11, 30))
    assert (november["total_idr"], november["transaction_count"]) == (2000, 1)
    res = service.restore_expense(settings, repo, env, ids["E4"])
    assert res["status"] == "restored"
    november = report(settings, repo, date(2026, 11, 1), date(2026, 11, 30))
    assert (november["total_idr"], november["transaction_count"]) == (20000, 2)


def test_update_adjusts_total(settings, seeded):
    repo, ids = seeded
    env = make_envelope(message_id="wa-upd")
    res = service.update_expense(
        settings, repo, env, ids["E1"], ExpensePatch(amount_idr=15000))
    assert res["status"] == "updated"
    october = report(settings, repo, date(2026, 10, 1), date(2026, 10, 31))
    assert october["total_idr"] == 65000
    assert october["transaction_count"] == 2


def test_unauthorized_chat(settings, seeded):
    repo, _ = seeded
    env = make_envelope(message_id="wa-x", chat_id="someone-else")
    res = service.get_report(settings, repo, env, ReportRequest(
        period="custom", start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31)))
    assert res["ok"] is False and res["status"] == "unauthorized"  # T21
