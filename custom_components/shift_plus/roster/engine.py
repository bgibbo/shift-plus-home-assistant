"""Deterministic roster evaluator backed by the shared Shift + contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Duty:
    date: date
    roster_id: str
    unit_id: str
    cycle_day: int
    cycle_length: int
    code: str
    category: str
    time_label: str | None
    recovery_label: str | None
    mandatory_rest: bool
    operational_verification: bool
    break_minutes: int | None

    @property
    def working(self) -> bool:
        return (
            self.category not in {"rest", "annualLeave", "unknown"}
            and not self.mandatory_rest
        )

    def roster_range(self) -> tuple[datetime, datetime] | None:
        if not self.time_label:
            return None
        try:
            start_text, end_text = self.time_label.split("-")
            start_hour, start_minute = (int(value) for value in start_text.split(":"))
            end_hour, end_minute = (int(value) for value in end_text.split(":"))
        except (ValueError, TypeError):
            return None
        start = datetime.combine(self.date, time(start_hour, start_minute))
        if end_hour == 24:
            end = datetime.combine(self.date + timedelta(days=1), time(0, end_minute))
        else:
            end = datetime.combine(self.date, time(end_hour, end_minute))
            if end <= start:
                end += timedelta(days=1)
        return start, end


class RosterEngine:
    """Evaluate built-in rosters from the Dart-generated shared definition."""

    def __init__(self, definition_path: Path | None = None) -> None:
        path = definition_path or Path(__file__).with_name("roster_definitions.v1.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("schema") != "ie.shiftplus.rosters"
            or payload.get("version") != 1
        ):
            raise ValueError("Unsupported Shift + roster definition")
        self.definition_version = int(payload["version"])
        self._rosters: dict[str, dict[str, Any]] = {
            item["id"]: item for item in payload["rosters"]
        }

    @property
    def roster_ids(self) -> tuple[str, ...]:
        return tuple(self._rosters)

    def roster(self, roster_id: str) -> dict[str, Any]:
        try:
            return self._rosters[roster_id]
        except KeyError as error:
            raise ValueError(f"Unknown roster: {roster_id}") from error

    def unit_ids(self, roster_id: str) -> tuple[str, ...]:
        return tuple(item["id"] for item in self.roster(roster_id)["units"])

    def duty(self, day: date, roster_id: str, unit_id: str) -> Duty:
        roster = self.roster(roster_id)
        unit = next((item for item in roster["units"] if item["id"] == unit_id), None)
        if unit is None:
            raise ValueError(f"Unknown unit {unit_id} for {roster_id}")
        anchor = date.fromisoformat(roster["anchor_date"])
        elapsed = (day - anchor).days
        raw = unit["days"][elapsed % int(roster["pattern_period"])]
        return Duty(
            date=day,
            roster_id=roster_id,
            unit_id=unit_id,
            cycle_day=elapsed % int(roster["cycle_length"]) + 1,
            cycle_length=int(roster["cycle_length"]),
            code=raw["code"],
            category=raw["category"],
            time_label=raw.get("time"),
            recovery_label=raw.get("recovery_label"),
            mandatory_rest=bool(raw.get("mandatory_rest", False)),
            operational_verification=bool(raw.get("operational_verification", False)),
            break_minutes=raw.get("break_minutes"),
        )

    def next_working_duty(
        self, after: date, roster_id: str, unit_id: str, *, include_today: bool = False
    ) -> Duty:
        start = 0 if include_today else 1
        for offset in range(start, 371):
            duty = self.duty(after + timedelta(days=offset), roster_id, unit_id)
            if duty.working:
                return duty
        raise RuntimeError("No calculable working duty in the next year")


def date_only(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)
