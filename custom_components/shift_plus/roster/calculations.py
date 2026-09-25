"""Book-on/off, leave and overtime calculations for Home Assistant."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo

from .engine import Duty, RosterEngine


@dataclass(frozen=True, slots=True)
class WorkBoundaries:
    roster_start: datetime | None
    roster_end: datetime | None
    effective_start: datetime | None
    effective_end: datetime | None
    booking_on_opens: datetime | None
    booking_on_closes: datetime | None
    booking_off_opens: datetime | None
    booking_off_closes: datetime | None
    book_on_alarm: datetime | None
    book_off_alarm: datetime | None


def work_boundaries(
    duty: Duty,
    *,
    overtime: dict | None = None,
    leave_portion: str | None = None,
    include_briefing: bool = False,
    book_on_offset_minutes: int = 8,
    book_off_offset_minutes: int = 8,
    time_zone: tzinfo = UTC,
) -> WorkBoundaries:
    roster = duty.roster_range()
    roster_start, roster_end = (
        tuple(localize(value, time_zone) for value in roster)
        if roster
        else (None, None)
    )
    overtime_start, overtime_end = _overtime_range(
        duty.date, overtime, time_zone=time_zone
    )
    if not duty.working and overtime is None:
        roster_start = roster_end = None
    start = roster_start or overtime_start
    end = roster_end or overtime_end
    overtime_before = bool(
        overtime_start and roster_start and overtime_start < roster_start
    )
    if overtime_before:
        start = overtime_start
    elif (
        start
        and include_briefing
        and duty.roster_id not in {"garda-staff", "personal-schedule"}
    ):
        start -= timedelta(minutes=15)
    if overtime_end and (end is None or overtime_end > end):
        end = overtime_end
    if leave_portion == "fullDay" and overtime is None:
        start = end = None
    book_on_applies = leave_portion != "morning"
    book_off_applies = leave_portion != "afternoon"
    on_open = start - timedelta(minutes=14) if start and book_on_applies else None
    on_close = start - timedelta(minutes=1) if start and book_on_applies else None
    off_open = end - timedelta(minutes=14) if end and book_off_applies else None
    off_close = end - timedelta(minutes=1) if end and book_off_applies else None
    return WorkBoundaries(
        roster_start=roster_start,
        roster_end=roster_end,
        effective_start=start,
        effective_end=end,
        booking_on_opens=on_open,
        booking_on_closes=on_close,
        booking_off_opens=off_open,
        booking_off_closes=off_close,
        book_on_alarm=start - timedelta(minutes=book_on_offset_minutes)
        if start and book_on_applies
        else None,
        book_off_alarm=end - timedelta(minutes=book_off_offset_minutes)
        if end and book_off_applies
        else None,
    )


def localize(value: datetime, time_zone: tzinfo) -> datetime:
    """Interpret a roster wall-clock value in the Home Assistant timezone."""
    if value.tzinfo is not None:
        return value.astimezone(time_zone)
    return value.replace(tzinfo=time_zone)


def _overtime_range(
    day: date, item: dict | None, *, time_zone: tzinfo = UTC
) -> tuple[datetime | None, datetime | None]:
    if not item:
        return None, None
    start_minutes = int(item["start_minutes"])
    finish_minutes = int(item["finish_minutes"])
    start = datetime(day.year, day.month, day.day) + timedelta(minutes=start_minutes)
    finish = datetime(day.year, day.month, day.day) + timedelta(minutes=finish_minutes)
    if finish <= start:
        finish += timedelta(days=1)
    return localize(start, time_zone), localize(finish, time_zone)


def pay_period(day: date) -> tuple[date, date]:
    end_anchor = date(2026, 8, 30)
    start_anchor = end_anchor - timedelta(days=27)
    start = day - timedelta(days=(day - start_anchor).days % 28)
    return start, start + timedelta(days=27)


def overtime_minutes(item: dict) -> int:
    start = int(item["start_minutes"])
    finish = int(item["finish_minutes"])
    if finish <= start:
        finish += 24 * 60
    return finish - start


def leave_for_date(records: Iterable[dict], day: date) -> dict | None:
    for item in records:
        start = date.fromisoformat(item["start_date"])
        if start <= day < start + timedelta(days=int(item["number_of_days"])):
            return item
    return None


def overtime_for_date(records: Iterable[dict], day: date) -> dict | None:
    return next((item for item in records if item["date"] == day.isoformat()), None)


def next_boundary(
    engine: RosterEngine,
    *,
    after: datetime,
    roster_id: str,
    unit_id: str,
    overtime: list[dict],
    leave: list[dict],
    include_briefing: bool,
    which: str,
    time_zone: tzinfo = UTC,
) -> datetime | None:
    for offset in range(0, 371):
        day = after.date() + timedelta(days=offset)
        duty = engine.duty(day, roster_id, unit_id)
        leave_item = leave_for_date(leave, day)
        bounds = work_boundaries(
            duty,
            overtime=overtime_for_date(overtime, day),
            leave_portion=leave_item.get("day_portion") if leave_item else None,
            include_briefing=include_briefing,
            time_zone=time_zone,
        )
        candidate = bounds.effective_start if which == "on" else bounds.effective_end
        if candidate and candidate > after:
            return candidate
    return None


def leave_totals(
    engine: RosterEngine,
    *,
    today: date,
    roster_id: str,
    unit_id: str,
    records: list[dict],
    start_month: int = 1,
    start_day: int = 1,
    opening_remaining: float = 35,
    carry_over: float = 0,
) -> tuple[float, float, float]:
    candidate = date(today.year, start_month, min(start_day, 28))
    year_start = (
        candidate
        if today >= candidate
        else date(today.year - 1, start_month, min(start_day, 28))
    )
    next_start = date(year_start.year + 1, start_month, min(start_day, 28))
    taken = planned = 0.0
    charged: dict[date, float] = {}
    for item in records:
        start = date.fromisoformat(item["start_date"])
        charge = 1.0 if item.get("day_portion", "fullDay") == "fullDay" else 0.5
        for offset in range(int(item["number_of_days"])):
            day = start + timedelta(days=offset)
            if not year_start <= day < next_start:
                continue
            if not engine.duty(day, roster_id, unit_id).working:
                continue
            charged[day] = min(1.0, charged.get(day, 0.0) + charge)
    for day, value in charged.items():
        if day < today:
            taken += value
        else:
            planned += value
    return taken, planned, opening_remaining + carry_over - taken - planned
