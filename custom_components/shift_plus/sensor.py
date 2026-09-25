"""Shift + sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime

from .coordinator import RuntimeData
from .entity import ShiftPlusEntity
from .roster.calculations import overtime_minutes


@dataclass(frozen=True, kw_only=True)
class ShiftPlusSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _iso(value: datetime | None) -> datetime | None:
    return value


SENSORS = (
    ShiftPlusSensorDescription(
        key="current_shift",
        name="Current shift",
        value_fn=lambda d: d["duty"].category,
        attrs_fn=lambda d: {
            "code": d["duty"].code,
            "rostered_time": d["duty"].time_label,
        },
    ),
    ShiftPlusSensorDescription(
        key="next_shift",
        name="Next shift",
        value_fn=lambda d: d["next_duty"].category,
        attrs_fn=lambda d: {
            "code": d["next_duty"].code,
            "date": d["next_duty"].date.isoformat(),
            "rostered_time": d["next_duty"].time_label,
        },
    ),
    ShiftPlusSensorDescription(
        key="next_shift_date",
        name="Next shift date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: d["next_duty"].date,
    ),
    ShiftPlusSensorDescription(
        key="roster_day",
        name="Roster day",
        value_fn=lambda d: d["duty"].cycle_day,
        attrs_fn=lambda d: {"cycle_length": d["duty"].cycle_length},
    ),
    ShiftPlusSensorDescription(
        key="active_roster", name="Active roster", value_fn=lambda d: d["roster_id"]
    ),
    ShiftPlusSensorDescription(
        key="active_unit", name="Active unit", value_fn=lambda d: d["unit_id"]
    ),
    ShiftPlusSensorDescription(
        key="rostered_start",
        name="Rostered shift start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].roster_start),
    ),
    ShiftPlusSensorDescription(
        key="rostered_end",
        name="Rostered shift end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].roster_end),
    ),
    ShiftPlusSensorDescription(
        key="effective_start",
        name="Effective work start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].effective_start),
    ),
    ShiftPlusSensorDescription(
        key="effective_end",
        name="Effective work end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].effective_end),
    ),
    ShiftPlusSensorDescription(
        key="next_book_on",
        name="Next Book On",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["next_book_on"]),
    ),
    ShiftPlusSensorDescription(
        key="next_book_off",
        name="Next Book Off",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["next_book_off"]),
    ),
    ShiftPlusSensorDescription(
        key="booking_on_opens",
        name="Booking-on window opens",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].booking_on_opens),
    ),
    ShiftPlusSensorDescription(
        key="booking_on_closes",
        name="Booking-on window closes",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].booking_on_closes),
    ),
    ShiftPlusSensorDescription(
        key="booking_off_opens",
        name="Booking-off window opens",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].booking_off_opens),
    ),
    ShiftPlusSensorDescription(
        key="booking_off_closes",
        name="Booking-off window closes",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso(d["boundaries"].booking_off_closes),
    ),
    ShiftPlusSensorDescription(
        key="previous_overtime",
        name="Previous 28-day overtime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: d["overtime_totals"][0],
    ),
    ShiftPlusSensorDescription(
        key="current_overtime",
        name="Current 28-day overtime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: d["overtime_totals"][1],
    ),
    ShiftPlusSensorDescription(
        key="next_overtime",
        name="Next known 28-day overtime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: d["overtime_totals"][2],
    ),
    ShiftPlusSensorDescription(
        key="leave_taken",
        name="Leave taken",
        native_unit_of_measurement="d",
        value_fn=lambda d: d["leave_totals"][0],
    ),
    ShiftPlusSensorDescription(
        key="leave_planned",
        name="Leave planned",
        native_unit_of_measurement="d",
        value_fn=lambda d: d["leave_totals"][1],
    ),
    ShiftPlusSensorDescription(
        key="leave_remaining",
        name="Leave remaining",
        native_unit_of_measurement="d",
        value_fn=lambda d: d["leave_totals"][2],
    ),
    ShiftPlusSensorDescription(
        key="last_sync",
        name="Last successful sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (
            datetime.fromisoformat(d["last_sync"]) if d.get("last_sync") else None
        ),
    ),
    ShiftPlusSensorDescription(
        key="pending_changes",
        name="Unacknowledged Home Assistant changes",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["pending_changes"],
    ),
    ShiftPlusSensorDescription(
        key="journal_awaiting_ack",
        name="Journal entries awaiting acknowledgement",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["journal_awaiting_ack"],
    ),
    ShiftPlusSensorDescription(
        key="conflicts",
        name="Sync conflicts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["conflicts"],
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        [ShiftPlusSensor(runtime, description) for description in SENSORS]
        + [AndroidPairingStatusSensor(runtime)]
        + [
            CompatibilitySummarySensor(runtime, key)
            for key in ("paired_devices", "calendar", "annual_leave", "overtime")
        ]
    )


class AndroidPairingStatusSensor(ShiftPlusEntity, SensorEntity):
    _attr_name = "Android pairing status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ready", "qr_available", "paired", "expired"]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime: RuntimeData) -> None:
        super().__init__(runtime.coordinator, "android_pairing_status")
        self.runtime = runtime

    @property
    def native_value(self) -> str:
        return self.runtime.pairing_status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        active = sum(
            1
            for device in self.runtime.store.paired_devices.values()
            if not device.get("revoked")
        )
        return {
            "paired_devices": active,
            "qr_expires_at": self.runtime.pairing_qr_expires_at.isoformat()
            if self.runtime.pairing_qr_expires_at
            else None,
        }


class ShiftPlusSensor(ShiftPlusEntity, SensorEntity):
    entity_description: ShiftPlusSensorDescription

    def __init__(
        self, runtime: RuntimeData, description: ShiftPlusSensorDescription
    ) -> None:
        super().__init__(runtime.coordinator, description.key)
        self.runtime = runtime
        self.entity_description = description

    @property
    def native_value(self):
        data = dict(self.coordinator.data)
        data["last_sync"] = self.runtime.store.last_successful_sync
        data["pending_changes"] = self.runtime.store.sync.outbound_unacknowledged_count
        data["journal_awaiting_ack"] = (
            self.runtime.store.sync.journal_awaiting_ack_count
        )
        data["conflicts"] = len(self.runtime.store.sync.conflicts)
        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key == "last_sync":
            return {
                "sync_status": self.runtime.store.sync_status,
                "sync_requested_at": self.runtime.store.sync_requested_at,
                **self.runtime.store.sync_details,
            }
        if self.entity_description.key == "pending_changes":
            return {
                "description": (
                    "Home Assistant-originated changes not yet acknowledged "
                    "by every paired Android replica"
                )
            }
        if self.entity_description.key == "journal_awaiting_ack":
            return {
                "description": (
                    "Protocol journal entries retained until Android returns "
                    "a newer server cursor"
                )
            }
        if self.entity_description.key == "conflicts":
            return {"unresolved": self.runtime.store.sync.conflict_summaries()}
        return (
            self.entity_description.attrs_fn(self.coordinator.data)
            if self.entity_description.attrs_fn
            else None
        )


class CompatibilitySummarySensor(ShiftPlusEntity, SensorEntity):
    """Keep public 5.0.1 entity IDs available during and after upgrade."""

    def __init__(self, runtime: RuntimeData, key: str) -> None:
        super().__init__(runtime.coordinator, key)
        self.runtime = runtime
        self.key = key
        self._attr_name = {
            "paired_devices": "Paired devices",
            "calendar": "Calendar",
            "annual_leave": "Annual leave",
            "overtime": "Overtime",
        }[key]

    @property
    def native_value(self):
        if self.key == "paired_devices":
            return sum(
                not item.get("revoked")
                for item in self.runtime.store.paired_devices.values()
            )
        if self.key == "calendar":
            return len(self.coordinator.data["leave"]) + len(
                self.coordinator.data["overtime"]
            )
        if self.key == "annual_leave":
            totals = self.coordinator.data["leave_totals"]
            return totals[0] + totals[1]
        return round(
            sum(overtime_minutes(item) for item in self.coordinator.data["overtime"])
            / 60,
            2,
        )

    @property
    def extra_state_attributes(self):
        if self.key == "paired_devices":
            return {
                "sync_status": self.runtime.store.sync_status,
                "premium_status": "active"
                if any(
                    not item.get("revoked")
                    for item in self.runtime.store.paired_devices.values()
                )
                else "inactive",
                "server_cursor": self.runtime.store.sync.cursor,
                "stored_records": len(self.runtime.store.sync.records),
            }
        if self.key == "calendar":
            return {"duty_data_available": True}
        if self.key == "annual_leave":
            totals = self.coordinator.data["leave_totals"]
            return {"taken": totals[0], "planned": totals[1], "remaining": totals[2]}
        return {"entries": len(self.coordinator.data["overtime"])}
