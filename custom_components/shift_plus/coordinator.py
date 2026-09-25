"""Runtime coordinator for calculated Shift + state."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import segno
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BOOK_OFF_OFFSET,
    CONF_BOOK_ON_OFFSET,
    CONF_INCLUDE_BRIEFING,
    CONF_ROSTER_ID,
    CONF_UNIT_ID,
    DOMAIN,
)
from .roster.calculations import (
    leave_for_date,
    leave_totals,
    next_boundary,
    overtime_for_date,
    overtime_minutes,
    pay_period,
    work_boundaries,
)
from .roster.engine import Duty, RosterEngine
from .storage import ShiftPlusStore


@dataclass(slots=True)
class RuntimeData:
    coordinator: ShiftPlusCoordinator
    store: ShiftPlusStore
    pairing: Any = None
    pairing_payload: dict[str, Any] | None = None
    pairing_qr: bytes | None = None
    pairing_qr_generated_at: datetime | None = None
    pairing_qr_expires_at: datetime | None = None
    pairing_qr_expired: bool = False

    def clear_pairing_qr(self, *, expired: bool = False) -> None:
        self.pairing_payload = None
        self.pairing_qr = None
        self.pairing_qr_generated_at = None
        self.pairing_qr_expires_at = None
        self.pairing_qr_expired = expired

    def expire_pairing_qr(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        if self.pairing_qr_expires_at is None or self.pairing_qr_expires_at > now:
            return False
        self.clear_pairing_qr(expired=True)
        return True

    @property
    def pairing_status(self) -> str:
        self.expire_pairing_qr()
        if self.pairing_qr_expired:
            return "expired"
        if self.pairing_qr is not None:
            return "qr_available"
        if any(not item.get("revoked") for item in self.store.paired_devices.values()):
            return "paired"
        return "ready"


class ShiftPlusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, store: ShiftPlusStore
    ) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self.entry = entry
        self.store = store
        self.engine = RosterEngine()
        self.time_zone = dt_util.get_time_zone(hass.config.time_zone) or UTC

    @property
    def config(self) -> dict[str, Any]:
        config = {**self.entry.data, **self.entry.options}
        # Public 5.0.1 entries did not contain schedule defaults. They are used
        # only until the synchronized active_configuration record is available.
        config.setdefault(CONF_ROSTER_ID, "core")
        config.setdefault(CONF_UNIT_ID, "unit-a")
        active = self.store.records("active_configuration")
        if active:
            payload = active[0]
            config[CONF_ROSTER_ID] = payload.get(
                "active_roster_id", config[CONF_ROSTER_ID]
            )
            config[CONF_UNIT_ID] = payload.get("active_unit_id", config[CONF_UNIT_ID])
            config[CONF_INCLUDE_BRIEFING] = payload.get(
                "include_tour_briefing", config.get(CONF_INCLUDE_BRIEFING, False)
            )
            config["roster_schedule_settings"] = payload.get(
                "roster_schedule_settings", config.get("roster_schedule_settings")
            )
        return config

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.now(self.time_zone)
        config = self.config
        roster_id = config[CONF_ROSTER_ID]
        unit_id = config[CONF_UNIT_ID]
        leave = self.store.records("annual_leave")
        overtime = self.store.records("overtime")
        duty = self._configured(self.engine.duty(now.date(), roster_id, unit_id))
        tomorrow = self._configured(
            self.engine.duty(now.date() + timedelta(days=1), roster_id, unit_id)
        )
        next_duty = self.engine.next_working_duty(now.date(), roster_id, unit_id)
        next_duty = self._configured(next_duty)
        leave_today = leave_for_date(leave, now.date())
        overtime_today = overtime_for_date(overtime, now.date())
        boundaries = work_boundaries(
            duty,
            overtime=overtime_today,
            leave_portion=leave_today.get("day_portion") if leave_today else None,
            include_briefing=bool(config.get(CONF_INCLUDE_BRIEFING, False)),
            book_on_offset_minutes=int(config.get(CONF_BOOK_ON_OFFSET, 8)),
            book_off_offset_minutes=int(config.get(CONF_BOOK_OFF_OFFSET, 8)),
            time_zone=self.time_zone,
        )
        period_start, period_end = pay_period(now.date())
        calculated_leave = leave_totals(
            self.engine,
            today=now.date(),
            roster_id=roster_id,
            unit_id=unit_id,
            records=leave,
            start_month=int(config.get("leave_year_start_month", 1)),
            start_day=int(config.get("leave_year_start_day", 1)),
            opening_remaining=float(config.get("leave_opening_remaining", 35)),
            carry_over=float(config.get("leave_carry_over", 0)),
        )
        period_totals: list[int] = []
        for shift in (-28, 0, 28):
            start = period_start + timedelta(days=shift)
            end = period_end + timedelta(days=shift)
            period_totals.append(
                sum(
                    overtime_minutes(item)
                    for item in overtime
                    if start <= date.fromisoformat(item["date"]) <= end
                )
            )
        return {
            "now": now,
            "duty": duty,
            "tomorrow": tomorrow,
            "next_duty": next_duty,
            "boundaries": boundaries,
            "next_book_on": next_boundary(
                self.engine,
                after=now,
                roster_id=roster_id,
                unit_id=unit_id,
                overtime=overtime,
                leave=leave,
                include_briefing=bool(config.get(CONF_INCLUDE_BRIEFING, False)),
                which="on",
                time_zone=self.time_zone,
            ),
            "next_book_off": next_boundary(
                self.engine,
                after=now,
                roster_id=roster_id,
                unit_id=unit_id,
                overtime=overtime,
                leave=leave,
                include_briefing=bool(config.get(CONF_INCLUDE_BRIEFING, False)),
                which="off",
                time_zone=self.time_zone,
            ),
            "working_now": bool(
                boundaries.effective_start
                and boundaries.effective_end
                and boundaries.effective_start <= now <= boundaries.effective_end
            ),
            "leave_today": leave_today,
            "overtime_today": overtime_today,
            "overtime_totals": period_totals,
            "leave_totals": calculated_leave,
            "leave": leave,
            "overtime": overtime,
            "roster_id": roster_id,
            "unit_id": unit_id,
        }

    def _configured(self, duty: Duty) -> Duty:
        config = self.config
        synced = _synced_time_label(duty, config.get("roster_schedule_settings"))
        if synced is not None:
            return replace(duty, time_label=synced)
        legacy = config.get(f"{duty.category}_time")
        if _valid_time_label(duty, legacy):
            return replace(duty, time_label=legacy)
        return duty


def _synced_time_label(duty: Duty, raw: Any) -> str | None:
    """Apply the Android schedule using the same precedence as the app."""
    if not isinstance(raw, dict):
        return None

    if duty.roster_id == "eight-hour":
        start = _minutes(raw.get("eightHourStartMinutes"))
        if start is not None:
            return _format_range(start, (start + 8 * 60) % (24 * 60))

    if duty.roster_id == "garda-staff":
        start = _minutes(raw.get("gardaStaffStartMinutes"))
        finish = _minutes(raw.get("gardaStaffFinishMinutes"))
        if start is not None and finish is not None and start != finish:
            return _format_range(start, finish)

    fields = {
        "early": ("earlyStartMinutes", "earlyFinishMinutes"),
        "late": ("lateStartMinutes", "lateFinishMinutes"),
        "night": ("nightStartMinutes", "nightFinishMinutes"),
    }.get(duty.category)
    if fields is not None:
        start = _minutes(raw.get(fields[0]))
        finish = _minutes(raw.get(fields[1]))
        if start is not None and finish is not None and start != finish:
            return _format_range(start, finish)

    if duty.roster_id.startswith("non-core-"):
        non_core_start = _minutes(raw.get("nonCoreStartMinutes"))
        duty_range = duty.roster_range()
        if non_core_start is not None and duty_range is not None:
            offset = non_core_start - 7 * 60
            start = duty_range[0].hour * 60 + duty_range[0].minute
            finish = duty_range[1].hour * 60 + duty_range[1].minute
            return _format_range(
                (start + offset) % (24 * 60),
                (finish + offset) % (24 * 60),
            )
    return None


def _minutes(value: Any) -> int | None:
    valid = isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 1440
    return value if valid else None


def _format_range(start: int, finish: int) -> str:
    def formatted(value: int) -> str:
        return f"{value // 60:02d}:{value % 60:02d}"

    return f"{formatted(start)}-{formatted(finish)}"


def _valid_time_label(duty: Duty, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return replace(duty, time_label=value).roster_range() is not None
    except ValueError:
        return False


def make_qr(payload: dict[str, Any]) -> bytes:
    import io

    output = io.BytesIO()
    segno.make(json.dumps(payload, separators=(",", ":"))).save(
        output, kind="png", scale=6, border=2
    )
    return output.getvalue()
