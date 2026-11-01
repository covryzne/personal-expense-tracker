"""Service layer: authorization, ownership injection, envelope shaping.

Every public function takes the trusted envelope, validates the sender
against server configuration, injects the owner user_id via the
repository, and returns the shared response envelope (TOOL_CONTRACT §3).
A success status is only returned with persisted rows from the DB.
"""
from __future__ import annotations

from datetime import timedelta

from . import idempotency
from .config import Settings
from .dates import day_bounds_utc, resolve_period
from .errors import FinanceError, Unauthorized, ValidationFailed
from .models import (
    CreateExpensesRequest,
    ExpensePatch,
    ListExpensesFilter,
    ReportRequest,
    TrustedEnvelope,
)


def _ok(status: str, data: dict) -> dict:
    return {"ok": True, "status": status, "data": data, "error": None}


def _err(exc: FinanceError) -> dict:
    return {
        "ok": False,
        "status": exc.code,
        "data": {},
        "error": {
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    }


def run(fn) -> dict:
    """Execute a service callable, converting errors to the envelope."""
    try:
        return fn()
    except FinanceError as exc:
        return _err(exc)
    except Exception as exc:  # validation from pydantic etc.
        return _err(ValidationFailed(str(exc)))


def _authorize(settings: Settings, envelope: TrustedEnvelope) -> None:
    if envelope.chat_id != settings.allowed_chat_id:
        raise Unauthorized("sender chat is not allowlisted")


def _public_row(row: dict) -> dict:
    out = {}
    for key, val in row.items():
        if hasattr(val, "isoformat"):
            out[key] = val.isoformat()
        else:
            out[key] = val
    out.pop("user_id", None)
    return out


def create_expenses(
    settings: Settings,
    repo,
    envelope: TrustedEnvelope,
    request: CreateExpensesRequest,
    *,
    derived_key: bool = False,
) -> dict:
    def _do() -> dict:
        _authorize(settings, envelope)
        if request.source_message_id != envelope.message_id:
            raise ValidationFailed(
                "source_message_id must come from the trusted envelope"
            )
        created, replayed, blocked = [], [], []
        for cand in sorted(
            request.expenses, key=lambda c: c.source_item_index
        ):
            row = {
                "occurred_at": cand.occurred_at,
                "amount_idr": cand.amount_idr,
                "category_code": cand.category_code,
                "description": cand.description,
                "merchant": cand.merchant,
                "payment_method": cand.payment_method,
                "source_type": envelope.source_type,
                "source_platform": request.source_platform,
                "source_message_id": request.source_message_id,
                "source_item_index": cand.source_item_index,
                "timestamp_basis": cand.timestamp_basis,
                "receipt_reference": cand.receipt_reference,
            }
            if derived_key:
                recent = repo.list_expenses(
                    start_utc=cand.occurred_at - timedelta(hours=24),
                    end_utc=cand.occurred_at + timedelta(seconds=1),
                    limit=50,
                )
                verdict = idempotency.assess_probable_duplicate(
                    row, recent, cand.occurred_at
                )
                if verdict is not None:
                    blocked.append({
                        "source_item_index": cand.source_item_index,
                        "probable_duplicate_of": verdict.expense_id,
                        "reason": verdict.reason,
                    })
                    continue
            stored, was_created = repo.insert_expense(row)
            (created if was_created else replayed).append(_public_row(stored))
        data = {
            "expenses": created + replayed,
            "created_count": len(created),
            "already_recorded_count": len(replayed),
            "probable_duplicates": blocked,
        }
        if blocked:
            return _ok("needs_clarification", data)
        if created:
            return _ok("created", data)
        return _ok("already_recorded", data)

    return run(_do)


def list_expenses(
    settings: Settings, repo, envelope: TrustedEnvelope,
    filters: ListExpensesFilter,
) -> dict:
    def _do() -> dict:
        _authorize(settings, envelope)
        start_utc = end_utc = None
        if filters.from_date is not None:
            start_utc, _ = day_bounds_utc(filters.from_date)
        if filters.to_date is not None:
            _, end_utc = day_bounds_utc(filters.to_date)
        rows = repo.list_expenses(
            start_utc=start_utc,
            end_utc=end_utc,
            category_code=filters.category_code,
            merchant_contains=filters.merchant_contains,
            limit=filters.limit,
        )
        return _ok(
            "found" if rows else "not_found",
            {"expenses": [_public_row(r) for r in rows], "count": len(rows)},
        )

    return run(_do)


def update_expense(
    settings: Settings, repo, envelope: TrustedEnvelope,
    expense_id: str, patch: ExpensePatch,
) -> dict:
    def _do() -> dict:
        _authorize(settings, envelope)
        updates = patch.to_update_dict()
        if not updates:
            raise ValidationFailed("patch is empty")
        row = repo.update_expense(expense_id, updates)
        return _ok("updated", {"expense": _public_row(row)})

    return run(_do)


def delete_expense(
    settings: Settings, repo, envelope: TrustedEnvelope, expense_id: str
) -> dict:
    def _do() -> dict:
        _authorize(settings, envelope)
        result = repo.set_deleted(expense_id, True)
        return _ok("deleted", {
            "expense_id": expense_id,
            "already_in_state": result == "already_in_state",
        })

    return run(_do)


def restore_expense(
    settings: Settings, repo, envelope: TrustedEnvelope, expense_id: str
) -> dict:
    def _do() -> dict:
        _authorize(settings, envelope)
        result = repo.set_deleted(expense_id, False)
        return _ok("restored", {
            "expense_id": expense_id,
            "already_in_state": result == "already_in_state",
        })

    return run(_do)


def get_report(
    settings: Settings, repo, envelope: TrustedEnvelope,
    request: ReportRequest,
) -> dict:
    def _do() -> dict:
        _authorize(settings, envelope)
        start_d, end_d, start_utc, end_utc = resolve_period(
            request.period,
            envelope.sent_at,
            request.start_date,
            request.end_date,
            max_range_days=settings.report_max_range_days,
        )
        raw = repo.report(start_utc, end_utc, request.category_code)
        data = {
            "timezone": "Asia/Jakarta",
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "total_idr": int(raw.get("total_idr") or 0),
            "transaction_count": int(raw.get("transaction_count") or 0),
            "by_category": [
                {
                    "category_code": b["category_code"],
                    "amount_idr": int(b["amount_idr"]),
                    "count": int(b["count"]),
                }
                for b in (raw.get("by_category") or [])
            ],
        }
        return _ok("found", data)

    return run(_do)
