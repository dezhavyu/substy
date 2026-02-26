from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolve_timezone(timezone_name: str) -> tuple[ZoneInfo, bool]:
    try:
        return ZoneInfo(timezone_name), True
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC"), False


def is_in_quiet_hours(local_time: time, start: time, end: time) -> bool:
    if start == end:
        return False

    current = local_time.replace(tzinfo=None)
    start = start.replace(tzinfo=None)
    end = end.replace(tzinfo=None)

    if start < end:
        return start <= current < end

    return current >= start or current < end


def compute_next_allowed_time(
    now_utc: datetime,
    timezone_name: str,
    quiet_hours_start: time,
    quiet_hours_end: time,
) -> datetime:
    if now_utc.tzinfo is None or now_utc.tzinfo.utcoffset(now_utc) is None:
        raise ValueError("now_utc must be timezone-aware")

    tz, _ = resolve_timezone(timezone_name)
    local_now = now_utc.astimezone(tz)
    local_time = local_now.time().replace(tzinfo=None)

    if not is_in_quiet_hours(local_time, quiet_hours_start, quiet_hours_end):
        return now_utc.astimezone(UTC)

    end_date = _compute_quiet_end_date(local_now.date(), local_time, quiet_hours_start, quiet_hours_end)
    local_end = datetime.combine(end_date, quiet_hours_end, tzinfo=tz)
    return local_end.astimezone(UTC)


def _compute_quiet_end_date(
    current_date: date,
    local_time: time,
    quiet_hours_start: time,
    quiet_hours_end: time,
) -> date:
    start = quiet_hours_start.replace(tzinfo=None)
    end = quiet_hours_end.replace(tzinfo=None)

    if start < end:
        return current_date

    if local_time >= start:
        return current_date + timedelta(days=1)

    return current_date
