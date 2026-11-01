from datetime import datetime
from zoneinfo import ZoneInfo

from finance.confirmation import report_message, saved_message

WIB = ZoneInfo("Asia/Jakarta")


def test_saved_message_format():
    row = {
        "id": "51188190-aaaa-bbbb-cccc-dddddddddddd",
        "description": "Matcha Coffee Original", "amount_idr": 12000,
        "category_code": "food_drink",
        "occurred_at": datetime(2026, 10, 30, 12, 51, tzinfo=WIB),
    }
    msg = saved_message([row], [])
    assert msg.startswith("Tercatat: Matcha Coffee Original · Rp12.000")
    assert "30 Okt 2026" in msg and "51188190" in msg


def test_report_message_zero_rows():
    data = {"start_date": "2026-09-01", "end_date": "2026-09-30",
            "total_idr": 0, "transaction_count": 0, "by_category": []}
    msg = report_message(data)
    assert "belum ada catatan" in msg  # T20: never claim real spending = 0
