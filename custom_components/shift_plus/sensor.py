"""Dashboard-safe sensors for Shift +."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NAME
from .crypto import entitlement_is_active
from .entity_data import (
    active_configuration,
    calendar_events,
    leave_summary,
    overtime_summary,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ShiftPlusStatusSensor(entry, runtime),
            ShiftPlusActiveRosterSensor(entry, runtime),
            ShiftPlusCalendarSensor(entry, runtime),
            ShiftPlusLeaveSensor(entry, runtime),
            ShiftPlusOvertimeSensor(entry, runtime),
        ]
    )


class ShiftPlusSensor(SensorEntity):
    """Base entity linked to the Shift + device and store updates."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime: dict[str, Any], key: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": "Shift +",
            "model": "Android companion integration",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._runtime["store"].add_listener(self._handle_store_update)
        )

    @callback
    def _handle_store_update(self) -> None:
        self.async_write_ha_state()


class ShiftPlusStatusSensor(ShiftPlusSensor):
    """Expose pairing and synchronization status."""

    _attr_name = "Paired devices"
    _attr_icon = "mdi:calendar-sync"

    def __init__(self, entry: ConfigEntry, runtime: dict[str, Any]) -> None:
        super().__init__(entry, runtime, "paired_devices")

    @property
    def native_value(self) -> int:
        return len(self._runtime["store"].data["devices"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        store = self._runtime["store"]
        devices = store.data["devices"].values()
        active = any(_entitlement_active(device) for device in devices)
        sync_status = (
            "ready"
            if active
            else ("entitlement_expired" if store.data["devices"] else "not_paired")
        )
        return {
            "sync_status": sync_status,
            "premium_status": "active" if active else "inactive",
            "server_cursor": store.data["cursor"],
            "stored_records": len(store.data["records"]),
            "pairing_path": f"/api/shift_plus/{self._entry.entry_id}/pairing",
        }


class ShiftPlusActiveRosterSensor(ShiftPlusSensor):
    """Expose the active roster and unit identifiers."""

    _attr_name = "Active roster"
    _attr_icon = "mdi:calendar-account"

    def __init__(self, entry: ConfigEntry, runtime: dict[str, Any]) -> None:
        super().__init__(entry, runtime, "active_roster")

    @property
    def native_value(self) -> str:
        return active_configuration(self._runtime["store"].data).get(
            "roster_id", "unknown"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return active_configuration(self._runtime["store"].data)


class ShiftPlusCalendarSensor(ShiftPlusSensor):
    """Expose sanitized events consumed by the Shift + roster card."""

    _attr_name = "Calendar"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, entry: ConfigEntry, runtime: dict[str, Any]) -> None:
        super().__init__(entry, runtime, "calendar")

    @property
    def native_value(self) -> int:
        return len(calendar_events(self._runtime["store"].data))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "events": calendar_events(self._runtime["store"].data),
            "duty_data_available": False,
        }


class ShiftPlusLeaveSensor(ShiftPlusSensor):
    """Expose annual-leave totals and timing."""

    _attr_name = "Annual leave"
    _attr_icon = "mdi:beach"
    _attr_native_unit_of_measurement = "d"

    def __init__(self, entry: ConfigEntry, runtime: dict[str, Any]) -> None:
        super().__init__(entry, runtime, "annual_leave")

    @property
    def native_value(self) -> float:
        return float(leave_summary(self._runtime["store"].data)["days"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return leave_summary(self._runtime["store"].data)


class ShiftPlusOvertimeSensor(ShiftPlusSensor):
    """Expose synchronized overtime totals."""

    _attr_name = "Overtime"
    _attr_icon = "mdi:clock-plus-outline"
    _attr_native_unit_of_measurement = "h"

    def __init__(self, entry: ConfigEntry, runtime: dict[str, Any]) -> None:
        super().__init__(entry, runtime, "overtime")

    @property
    def native_value(self) -> float:
        return float(overtime_summary(self._runtime["store"].data)["hours"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return overtime_summary(self._runtime["store"].data)


def _entitlement_active(device: dict[str, Any]) -> bool:
    try:
        return entitlement_is_active(device)
    except (KeyError, TypeError, ValueError):
        return False
