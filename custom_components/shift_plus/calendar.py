"""Roster, overtime and annual-leave calendar entities."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .coordinator import RuntimeData
from .entity import ShiftPlusEntity
from .roster.calculations import localize


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        [
            ShiftPlusCalendar(runtime, kind)
            for kind in ("roster", "annual_leave", "overtime")
        ]
    )


class ShiftPlusCalendar(ShiftPlusEntity, CalendarEntity):
    def __init__(self, runtime: RuntimeData, kind: str) -> None:
        super().__init__(runtime.coordinator, f"calendar_{kind}")
        self.runtime = runtime
        self.kind = kind
        self._attr_name = {
            "roster": "Roster",
            "annual_leave": "Annual leave",
            "overtime": "Overtime",
        }[kind]

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now(self.runtime.coordinator.time_zone)
        events = self._events(now - timedelta(days=1), now + timedelta(days=60))
        return next((event for event in events if _has_not_ended(event, now)), None)

    async def async_get_events(
        self, hass, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return self._events(start_date, end_date)

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        if self.kind == "roster":
            events = []
            current = start.date()
            while current <= end.date():
                duty = self.runtime.coordinator._configured(
                    self.runtime.coordinator.engine.duty(
                        current,
                        self.coordinator.data["roster_id"],
                        self.coordinator.data["unit_id"],
                    )
                )
                duty_range = duty.roster_range()
                if duty.working and duty_range:
                    events.append(
                        CalendarEvent(
                            start=localize(
                                duty_range[0], self.runtime.coordinator.time_zone
                            ),
                            end=localize(
                                duty_range[1], self.runtime.coordinator.time_zone
                            ),
                            summary=f"{duty.code} shift",
                            description=duty.time_label,
                        )
                    )
                current += timedelta(days=1)
            return events
        if self.kind == "annual_leave":
            return sorted(
                [
                    CalendarEvent(
                        start=date.fromisoformat(item["start_date"]),
                        end=date.fromisoformat(item["start_date"])
                        + timedelta(days=int(item["number_of_days"])),
                        summary="Annual leave",
                        description=item["day_portion"],
                        uid=item["id"],
                    )
                    for item in self.runtime.store.records("annual_leave")
                ],
                key=lambda event: event.start,
            )
        result = []
        for item in self.runtime.store.records("overtime"):
            day = date.fromisoformat(item["date"])
            begin = datetime.combine(day, time()) + timedelta(
                minutes=int(item["start_minutes"])
            )
            finish = datetime.combine(day, time()) + timedelta(
                minutes=int(item["finish_minutes"])
            )
            if finish <= begin:
                finish += timedelta(days=1)
            result.append(
                CalendarEvent(
                    start=localize(begin, self.runtime.coordinator.time_zone),
                    end=localize(finish, self.runtime.coordinator.time_zone),
                    summary="Overtime",
                    description=item.get("description"),
                    uid=item["id"],
                )
            )
        return result


def _has_not_ended(event: CalendarEvent, now: datetime) -> bool:
    """Compare timed and all-day events without mixing datetime and date."""
    return event.end_datetime_local > now
