"""Safe entity projections over the replicated Shift + record store."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def live_records(data: dict[str, Any], record_type: str) -> list[dict[str, Any]]:
    """Return valid, live records of one type without protocol metadata."""
    records: list[dict[str, Any]] = []
    for value in data.get("records", {}).values():
        if (
            isinstance(value, dict)
            and value.get("record_type") == record_type
            and value.get("tombstone") is False
            and isinstance(value.get("payload"), dict)
        ):
            records.append(value["payload"])
    return records


def active_configuration(data: dict[str, Any]) -> dict[str, str]:
    """Project the non-sensitive active roster identifiers."""
    records = live_records(data, "active_configuration")
    if not records:
        return {}
    payload = records[-1]
    result: dict[str, str] = {}
    for source, target in (
        ("active_roster_id", "roster_id"),
        ("active_unit_id", "unit_id"),
    ):
        value = payload.get(source)
        if isinstance(value, str) and value.strip():
            result[target] = value.strip()
    return result


def calendar_events(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Create sanitized leave/overtime calendar events for dashboards."""
    events: list[dict[str, Any]] = []
    for payload in live_records(data, "annual_leave"):
        try:
            start = date.fromisoformat(str(payload["start_date"])[:10])
            days = int(payload["number_of_days"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 1 <= days <= 366:
            continue
        portion = payload.get("day_portion")
        for offset in range(days):
            event: dict[str, Any] = {
                "date": (start + timedelta(days=offset)).isoformat(),
                "kind": "annual_leave",
            }
            if portion in ("full", "firstHalf", "secondHalf"):
                event["portion"] = portion
            events.append(event)
    for payload in live_records(data, "overtime"):
        try:
            day = date.fromisoformat(str(payload["date"])[:10])
            start_minutes = int(payload["start_minutes"])
            finish_minutes = int(payload["finish_minutes"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= start_minutes < 1440 or not 0 <= finish_minutes < 1440:
            continue
        duration = (finish_minutes - start_minutes) % 1440 or 1440
        events.append(
            {
                "date": day.isoformat(),
                "kind": "overtime",
                "start_minutes": start_minutes,
                "finish_minutes": finish_minutes,
                "duration_minutes": duration,
            }
        )
    return sorted(events, key=lambda item: (item["date"], item["kind"]))


def leave_summary(data: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Summarize leave without exposing record IDs or notes."""
    current = today or date.today()
    leave = [
        event for event in calendar_events(data) if event["kind"] == "annual_leave"
    ]
    upcoming = [
        event["date"] for event in leave if event["date"] >= current.isoformat()
    ]
    days = sum(1 if event.get("portion") == "full" else 0.5 for event in leave)
    return {
        "days": days,
        "today": any(event["date"] == current.isoformat() for event in leave),
        "next_date": upcoming[0] if upcoming else None,
    }


def overtime_summary(data: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Summarize overtime duration and next date."""
    events = [event for event in calendar_events(data) if event["kind"] == "overtime"]
    minutes = sum(int(event["duration_minutes"]) for event in events)
    current = today or date.today()
    upcoming = [
        event["date"] for event in events if event["date"] >= current.isoformat()
    ]
    return {
        "hours": round(minutes / 60, 2),
        "entries": len(events),
        "next_date": upcoming[0] if upcoming else None,
    }
