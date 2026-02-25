"""
Post scheduler.
Distributes N posts across configured US peak-time windows,
then converts each slot to UTC for storage.

When AUTO_POST eventually replaces manual review, this file stays unchanged —
the only difference is posts are saved with status='approved' from the start.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def get_schedule_slots(count: int, schedule_config: dict) -> list[str]:
    """
    Return a list of `count` UTC ISO datetime strings, distributed across
    the configured peak-time posting windows.

    If more posts than windows, later posts are spaced 5 minutes after
    their window to avoid exact duplicates.

    Skips windows that have already passed today; if all have passed,
    uses tomorrow's first window.
    """
    tz_name = schedule_config.get("timezone", "America/New_York")
    windows = schedule_config.get("posting_windows", ["09:00", "12:00", "17:00", "19:00"])

    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    today = now_local.date()

    # Build datetime objects for each window (today, local tz)
    window_dts = []
    for w in windows:
        hour, minute = map(int, w.split(":"))
        dt = datetime(today.year, today.month, today.day, hour, minute, tzinfo=tz)
        if dt > now_local:
            window_dts.append(dt)

    # All windows have passed → use tomorrow's first window
    if not window_dts:
        tomorrow = today + timedelta(days=1)
        hour, minute = map(int, windows[0].split(":"))
        window_dts = [
            datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=tz)
        ]

    utc = ZoneInfo("UTC")
    slots = []

    for i in range(count):
        window = window_dts[i % len(window_dts)]
        # Multiple posts in the same window get a small spacing offset
        overflow = i // len(window_dts)
        if overflow > 0:
            window = window + timedelta(minutes=overflow * 5)
        slots.append(window.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    return slots


def add_stagger(utc_datetime_str: str, minutes: int) -> str:
    """
    Add `minutes` to a UTC ISO datetime string and return the result.
    Used to stagger Reddit posts after the matching X post.
    """
    utc = ZoneInfo("UTC")
    dt = datetime.strptime(utc_datetime_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utc)
    staggered = dt + timedelta(minutes=minutes)
    return staggered.strftime("%Y-%m-%dT%H:%M:%SZ")
