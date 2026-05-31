from datetime import datetime

from app.services.scheduler import parse_cron


def test_parse_default_daily_midnight():
    schedule = parse_cron("0 0 * * *")

    assert schedule.matches(datetime(2026, 5, 31, 0, 0))
    assert not schedule.matches(datetime(2026, 5, 31, 0, 1))
    assert not schedule.matches(datetime(2026, 5, 31, 1, 0))


def test_next_after_default_daily_midnight():
    schedule = parse_cron("0 0 * * *")

    assert schedule.next_after(datetime(2026, 5, 31, 10, 30)) == datetime(2026, 6, 1, 0, 0)


def test_parse_steps_and_weekday():
    schedule = parse_cron("*/15 8-10 * * 1-5")

    assert schedule.matches(datetime(2026, 6, 1, 8, 15))
    assert schedule.matches(datetime(2026, 6, 1, 10, 45))
    assert not schedule.matches(datetime(2026, 6, 1, 11, 0))
    assert not schedule.matches(datetime(2026, 5, 31, 8, 15))
