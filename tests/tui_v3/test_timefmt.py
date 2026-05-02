"""format_age maps timestamps to short relative strings."""
from datetime import datetime, timedelta, timezone

import pytest

from orca.tui.timefmt import format_age


@pytest.fixture
def now():
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("delta,expected", [
    (timedelta(seconds=5), "5s"),
    (timedelta(seconds=59), "59s"),
    (timedelta(minutes=3), "3m"),
    (timedelta(minutes=59), "59m"),
    (timedelta(hours=2), "2h"),
    (timedelta(hours=23), "23h"),
    (timedelta(days=2), "2d"),
    (timedelta(days=14), "14d"),
])
def test_format_age_buckets(delta, expected, now):
    iso = (now - delta).isoformat()
    assert format_age(iso, now=now) == expected


def test_format_age_none_returns_dash(now):
    assert format_age(None, now=now) == "-"


def test_format_age_invalid_returns_dash(now):
    assert format_age("not-an-iso-string", now=now) == "-"
