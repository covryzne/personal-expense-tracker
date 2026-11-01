from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from finance.dates import resolve_period
from finance.errors import ValidationFailed

WIB = ZoneInfo("Asia/Jakarta")


def ref(y, m, d, hh=10):
    return datetime(y, m, d, hh, 0, tzinfo=WIB)


def test_this_month_october():
    s, e, su, eu = resolve_period("this_month", ref(2026, 10, 15))
    assert (s, e) == (date(2026, 10, 1), date(2026, 10, 31))
    # E3 (2026-11-01 00:15 WIB) must fall OUTSIDE October (month boundary).
    e3_utc = datetime(2026, 10, 31, 17, 15, tzinfo=ZoneInfo("UTC"))
    assert not (su <= e3_utc < eu)


def test_this_week_starts_monday():
    # 2026-11-02 is a Monday.
    s, e, _, _ = resolve_period("this_week", ref(2026, 11, 4))
    assert s == date(2026, 11, 2) and e == date(2026, 11, 8)
    s, e, _, _ = resolve_period("last_week", ref(2026, 11, 4))
    assert s == date(2026, 10, 26) and e == date(2026, 11, 1)


def test_custom_range_validation():
    with pytest.raises(ValidationFailed):
        resolve_period("custom", ref(2026, 11, 2),
                       date(2026, 11, 10), date(2026, 11, 1))
    with pytest.raises(ValidationFailed):  # T29: beyond safe maximum
        resolve_period("custom", ref(2026, 11, 2),
                       date(2024, 1, 1), date(2026, 11, 1),
                       max_range_days=366)
