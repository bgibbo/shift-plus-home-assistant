from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from custom_components.shift_plus.calendar import ShiftPlusCalendar, _has_not_ended


class LeaveStore:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    def records(self, record_type: str) -> list[dict]:
        return self._records if record_type == "annual_leave" else []


def calendar_with(records: list[dict], now: datetime, monkeypatch) -> ShiftPlusCalendar:
    monkeypatch.setattr(
        "custom_components.shift_plus.calendar.dt_util.now",
        lambda requested_zone=None: now,
    )
    calendar = object.__new__(ShiftPlusCalendar)
    calendar.kind = "annual_leave"
    calendar.runtime = SimpleNamespace(
        coordinator=SimpleNamespace(time_zone=now.tzinfo), store=LeaveStore(records)
    )
    return calendar


def leave(record_id: str, start: date, days: int = 1, portion: str = "fullDay") -> dict:
    return {
        "id": record_id,
        "start_date": start.isoformat(),
        "number_of_days": days,
        "day_portion": portion,
    }


def test_current_all_day_leave_is_exposed_without_mixed_type_comparison(
    monkeypatch,
) -> None:
    zone = ZoneInfo("Europe/Dublin")
    now = datetime(2026, 9, 1, 12, tzinfo=zone)
    event = calendar_with([leave("current", now.date())], now, monkeypatch).event
    assert event is not None
    assert event.start == date(2026, 9, 1)
    assert event.end == date(2026, 9, 2)
    assert event.description == "fullDay"


def test_future_all_day_leave_is_exposed_as_next_event(monkeypatch) -> None:
    zone = ZoneInfo("Europe/Dublin")
    now = datetime(2026, 9, 1, 12, tzinfo=zone)
    event = calendar_with(
        [leave("future", date(2026, 9, 10), portion="morning")], now, monkeypatch
    ).event
    assert event is not None
    assert event.start == date(2026, 9, 10)
    assert event.description == "morning"


def test_no_leave_events_returns_none(monkeypatch) -> None:
    zone = ZoneInfo("Europe/Dublin")
    now = datetime(2026, 9, 1, 12, tzinfo=zone)
    assert calendar_with([], now, monkeypatch).event is None


def test_past_event_is_skipped_and_records_are_sorted(monkeypatch) -> None:
    zone = ZoneInfo("Europe/Dublin")
    now = datetime(2026, 9, 1, 12, tzinfo=zone)
    records = [leave("future", date(2026, 9, 20)), leave("past", date(2026, 8, 1))]
    assert calendar_with(records, now, monkeypatch).event.uid == "future"


def test_timezone_aware_now_compares_safely_with_all_day_end() -> None:
    from homeassistant.components.calendar import CalendarEvent

    zone = ZoneInfo("Europe/Dublin")
    now = datetime(2026, 9, 1, 23, 59, tzinfo=zone)
    event = CalendarEvent(
        start=date(2026, 9, 1), end=date(2026, 9, 2), summary="Annual leave"
    )
    assert _has_not_ended(event, now)
    assert not _has_not_ended(event, now + timedelta(days=1))
