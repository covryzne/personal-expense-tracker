import pytest

from finance.money import format_idr, parse_amount_idr


def test_format():
    assert format_idr(12000) == "Rp12.000"
    assert format_idr(62000) == "Rp62.000"
    assert format_idr(0) == "Rp0"
    assert format_idr(1500000) == "Rp1.500.000"


@pytest.mark.parametrize("text,expected", [
    ("12000", 12000),
    ("12.000", 12000),
    ("12.500", 12500),          # T02: never decimal 12.5
    ("Rp12.000", 12000),
    ("Rp 50.000", 50000),
    ("12rb", 12000),
    ("12 ribu", 12000),
    ("15k", 15000),
    ("50rb", 50000),
    ("1,5jt", 1500000),
    ("2 juta", 2000000),
])
def test_parse_valid(text, expected):
    assert parse_amount_idr(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "12.5", "-5000", "0rb", None])
def test_parse_invalid(text):
    assert parse_amount_idr(text) is None
