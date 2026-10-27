from datetime import date

import pytest

from channel_analytics import (
    ANALYTICS_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    format_duration,
    missing_required_scopes,
    reporting_date_range,
    rows_to_dicts,
)


def test_reporting_date_range_is_inclusive_and_accounts_for_reporting_lag():
    assert reporting_date_range(7, today=date(2026, 10, 28)) == (
        "2026-10-20", "2026-10-26"
    )


def test_reporting_date_range_can_use_zero_lag():
    assert reporting_date_range(1, today=date(2026, 10, 28), lag_days=0) == (
        "2026-10-28", "2026-10-28"
    )


@pytest.mark.parametrize("days", [0, -1, True, 1.5, "28"])
def test_reporting_date_range_rejects_invalid_day_counts(days):
    with pytest.raises(ValueError):
        reporting_date_range(days)  # type: ignore[arg-type]


def test_missing_required_scopes_lists_only_missing_read_permissions():
    assert missing_required_scopes({ANALYTICS_SCOPE, YOUTUBE_READONLY_SCOPE}) == set()
    assert missing_required_scopes({ANALYTICS_SCOPE}) == {YOUTUBE_READONLY_SCOPE}
    assert missing_required_scopes(set()) == {ANALYTICS_SCOPE, YOUTUBE_READONLY_SCOPE}


def test_rows_to_dicts_maps_column_names_to_each_row():
    payload = {
        "columnHeaders": [{"name": "day"}, {"name": "views"}, {"name": "likes"}],
        "rows": [["2026-10-01", 123, 7], ["2026-10-02", 456, 12, "extra"]],
    }
    assert rows_to_dicts(payload) == [
        {"day": "2026-10-01", "views": 123, "likes": 7},
        {"day": "2026-10-02", "views": 456, "likes": 12},
    ]


def test_rows_to_dicts_handles_empty_and_invalid_payloads():
    assert rows_to_dicts({"columnHeaders": [], "rows": None}) == []
    assert rows_to_dicts(None) == []


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0:00"), (9, "0:09"), (65, "1:05"), (3599, "59:59"), (3661, "1:01:01")],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_format_duration_handles_missing_and_invalid_values():
    assert format_duration(None) == "0:00"
    assert format_duration("not-a-number") == "0:00"
