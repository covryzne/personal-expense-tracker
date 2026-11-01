"""In-memory repository with the same contract as SupabaseRepository,
including SQL-equivalent report aggregation (for unit tests only)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from finance.errors import NotFound


class FakeRepository:
    def __init__(self):
        self.rows: dict[str, dict] = {}
        self._by_key: dict[tuple, str] = {}

    def insert_expense(self, row):
        key = (
            row["source_platform"], row["source_message_id"],
            row["source_item_index"],
        )
        if key in self._by_key:
            return dict(self.rows[self._by_key[key]]), False
        stored = dict(row)
        stored["id"] = str(uuid.uuid4())
        stored["created_at"] = datetime.now(timezone.utc)
        stored["updated_at"] = stored["created_at"]
        stored["deleted_at"] = None
        self.rows[stored["id"]] = stored
        self._by_key[key] = stored["id"]
        return dict(stored), True

    def list_expenses(self, *, start_utc=None, end_utc=None,
                      category_code=None, merchant_contains=None,
                      limit=10, include_deleted=False):
        out = []
        for r in self.rows.values():
            if not include_deleted and r["deleted_at"] is not None:
                continue
            if start_utc and r["occurred_at"] < start_utc:
                continue
            if end_utc and r["occurred_at"] >= end_utc:
                continue
            if category_code and r["category_code"] != category_code:
                continue
            if merchant_contains and merchant_contains.lower() not in (
                r.get("merchant") or ""
            ).lower():
                continue
            out.append(dict(r))
        out.sort(key=lambda r: (r["occurred_at"], r["id"]), reverse=True)
        return out[:limit]

    def get_expense(self, expense_id):
        r = self.rows.get(expense_id)
        return dict(r) if r else None

    def update_expense(self, expense_id, patch):
        r = self.rows.get(expense_id)
        if r is None or r["deleted_at"] is not None:
            raise NotFound("not found")
        r.update(patch)
        return dict(r)

    def set_deleted(self, expense_id, deleted):
        r = self.rows.get(expense_id)
        if r is None:
            raise NotFound("not found")
        already = (r["deleted_at"] is not None) == deleted
        if already:
            return "already_in_state"
        r["deleted_at"] = datetime.now(timezone.utc) if deleted else None
        return "changed"

    def report(self, start_utc, end_utc, category_code=None):
        total = 0
        count = 0
        by_cat: dict[str, dict] = {}
        for r in self.rows.values():
            if r["deleted_at"] is not None:
                continue
            if not (start_utc <= r["occurred_at"] < end_utc):
                continue
            if category_code and r["category_code"] != category_code:
                continue
            total += r["amount_idr"]
            count += 1
            g = by_cat.setdefault(
                r["category_code"],
                {"category_code": r["category_code"], "amount_idr": 0,
                 "count": 0},
            )
            g["amount_idr"] += r["amount_idr"]
            g["count"] += 1
        return {
            "total_idr": total,
            "transaction_count": count,
            "by_category": sorted(
                by_cat.values(), key=lambda b: -b["amount_idr"]
            ),
        }
