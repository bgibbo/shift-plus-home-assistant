from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from custom_components.shift_plus.roster.calculations import pay_period, work_boundaries
from custom_components.shift_plus.roster.engine import RosterEngine


def test_pay_period_uses_shared_28_day_anchor() -> None:
    assert pay_period(date(2026, 8, 9)) == (date(2026, 8, 3), date(2026, 8, 30))


def test_briefing_and_alarm_boundaries_are_distinct() -> None:
    duty = RosterEngine().next_working_duty(date(2026, 8, 9), "core", "unit-a")
    boundaries = work_boundaries(duty, include_briefing=True)
    assert boundaries.roster_start is not None
    assert boundaries.effective_start == boundaries.roster_start.replace(
        minute=boundaries.roster_start.minute
    ) - (boundaries.roster_start - boundaries.effective_start)
    assert (
        boundaries.roster_start - boundaries.effective_start
    ).total_seconds() == 15 * 60
    assert (
        boundaries.effective_start - boundaries.book_on_alarm
    ).total_seconds() == 8 * 60
    assert (
        boundaries.effective_start - boundaries.booking_on_opens
    ).total_seconds() == 14 * 60


def test_earlier_overtime_replaces_briefing_and_later_overtime_extends_finish() -> None:
    engine = RosterEngine()
    duty = engine.next_working_duty(date(2026, 8, 9), "core", "unit-a")
    roster = duty.roster_range()
    assert roster is not None
    overtime = {
        "start_minutes": max(0, roster[0].hour * 60 - 60),
        "finish_minutes": (roster[1].hour * 60 + roster[1].minute + 60) % 1440,
    }
    boundaries = work_boundaries(duty, overtime=overtime, include_briefing=True)
    assert boundaries.effective_start == datetime.combine(
        duty.date, datetime.min.time(), tzinfo=UTC
    ).replace(
        hour=overtime["start_minutes"] // 60, minute=overtime["start_minutes"] % 60
    )
    assert boundaries.effective_start < boundaries.roster_start


def test_boundaries_are_aware_in_home_assistant_timezone() -> None:
    zone = ZoneInfo("Europe/Dublin")
    duty = RosterEngine().next_working_duty(date(2026, 8, 9), "core", "unit-a")
    boundaries = work_boundaries(duty, include_briefing=True, time_zone=zone)

    values = (
        boundaries.roster_start,
        boundaries.roster_end,
        boundaries.effective_start,
        boundaries.effective_end,
        boundaries.booking_on_opens,
        boundaries.booking_on_closes,
        boundaries.booking_off_opens,
        boundaries.booking_off_closes,
        boundaries.book_on_alarm,
        boundaries.book_off_alarm,
    )
    assert all(value is None or value.tzinfo is zone for value in values)

    # This is the setup-time comparison that raised before the fix.
    aware_now = datetime(2026, 8, 10, 12, 0, tzinfo=zone)
    assert isinstance(boundaries.effective_start <= aware_now, bool)
