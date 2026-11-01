"""WhatsApp-facing message formats (TOOL_CONTRACT §10)."""
from __future__ import annotations

from datetime import date

from .categories import label_for
from .dates import format_instant_wib, format_local_date
from .money import format_idr


def short_id(expense_id: str) -> str:
    return expense_id.split("-")[0]


def saved_message(created: list[dict], replayed: list[dict]) -> str:
    lines = []
    for row in created:
        lines.append(
            f"Tercatat: {row['description']} · {format_idr(row['amount_idr'])}"
            f" · {label_for(row['category_code'])}"
            f" · {format_instant_wib(row['occurred_at'])}."
            f" ID {short_id(str(row['id']))}."
        )
    for row in replayed:
        lines.append(
            f"Transaksi ini sudah tercatat sebelumnya"
            f" (ID {short_id(str(row['id']))}), jadi nggak gua dobel."
        )
    return "\n".join(lines)


def report_message(data: dict) -> str:
    start = date.fromisoformat(data["start_date"])
    end = date.fromisoformat(data["end_date"])
    if start == end:
        span = format_local_date(start)
    else:
        span = f"{format_local_date(start)} – {format_local_date(end)}"
    count = data["transaction_count"]
    if count == 0:
        return (
            f"Laporan {span} (WIB): belum ada catatan pengeluaran"
            f" di periode ini."
        )
    top = max(data["by_category"], key=lambda b: b["amount_idr"])
    return (
        f"Laporan {span} (WIB): {count} transaksi,"
        f" total {format_idr(data['total_idr'])}."
        f" Terbesar: {label_for(top['category_code'])}"
        f" {format_idr(top['amount_idr'])}."
    )
