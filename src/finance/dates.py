"""WIB (Asia/Jakarta) period math. All boundaries are computed as local
calendar dates, then converted to UTC half-open instants (DATA_MODEL §4).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .errors import ValidationFailed

WIB = ZoneInfo("Asia/Jakarta")
UTC = timezone.utc

MONTH_ID = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]

PERIODS = (
    "today", "yesterday", "this_week", "last_week",
    "this_month", "last_month", "custom",
)


def to_wib(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise ValidationFailed("timestamp must be timezone-aware")
    return instant.astimezone(WIB)


def local_date(instant: datetime) -> date:
    return to_wib(instant).date()


def day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(d, time.min, tzinfo=WIB)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def resolve_period(
    period: str,
    reference: datetime,
    start_date: date | None = None,
    end_date: date | None = None,
    max_range_days: int = 366,
) -> tuple[date, date, datetime, datetime]:
    """Return (start_local, end_local_inclusive, start_utc, end_utc_excl)."""
    if period not in PERIODS:
        raise ValidationFailed(f"unknown period: {period}")
    today = local_date(reference)
    if period == "today":
        start = end = today
    elif period == "yesterday":
        start = end = today - timedelta(days=1)
    elif period == "this_week":
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)
    elif period == "last_week":
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
    elif period == "this_month":
        start = today.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        end = nxt - timedelta(days=1)
    elif period == "last_month":
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
    else:  # custom
        if start_date is None or end_date is None:
            raise ValidationFailed("custom period needs start_date and end_date")
        start, end = start_date, end_date
    if end < start:
        raise ValidationFailed("end_date precedes start_date")
    if (end - start).days + 1 > max_range_days:
        raise ValidationFailed(
            f"range exceeds configured maximum of {max_range_days} days"
        )
    start_utc, _ = day_bounds_utc(start)
    _, end_utc = day_bounds_utc(end)
    return start, end, start_utc, end_utc


def format_local_date(d: date) -> str:
    """date(2026,10,30) -> '30 Okt 2026'."""
    return f"{d.day} {MONTH_ID[d.month - 1]} {d.year}"


def format_instant_wib(instant) -> str:
    if isinstance(instant, str):
        instant = datetime.fromisoformat(instant.replace("Z", "+00:00"))
    return format_local_date(local_date(instant))
