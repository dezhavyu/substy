from datetime import UTC, datetime, time

from delivery_service.core.quiet_hours import compute_next_allowed_time, is_in_quiet_hours


def test_is_in_quiet_hours_for_regular_interval():
    assert is_in_quiet_hours(time(23, 0), time(22, 0), time(23, 30)) is True
    assert is_in_quiet_hours(time(21, 59), time(22, 0), time(23, 30)) is False
    assert is_in_quiet_hours(time(23, 30), time(22, 0), time(23, 30)) is False


def test_is_in_quiet_hours_for_cross_midnight_interval():
    assert is_in_quiet_hours(time(23, 0), time(22, 0), time(7, 0)) is True
    assert is_in_quiet_hours(time(6, 30), time(22, 0), time(7, 0)) is True
    assert is_in_quiet_hours(time(12, 0), time(22, 0), time(7, 0)) is False


def test_compute_next_allowed_time_cross_midnight():
    now = datetime(2026, 1, 1, 23, 15, tzinfo=UTC)
    next_allowed = compute_next_allowed_time(now, "UTC", time(22, 0), time(7, 0))
    assert next_allowed == datetime(2026, 1, 2, 7, 0, tzinfo=UTC)


def test_compute_next_allowed_time_when_allowed_now():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    next_allowed = compute_next_allowed_time(now, "UTC", time(22, 0), time(7, 0))
    assert next_allowed == now
