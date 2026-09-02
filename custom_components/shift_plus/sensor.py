"""Status sensor for Shift Plus."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, NAME


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [ShiftPlusStatusSensor(entry, hass.data[DOMAIN][entry.entry_id])]
    )


class ShiftPlusStatusSensor(SensorEntity):
    """Expose pairing and synchronization status."""

    _attr_has_entity_name = True
    _attr_name = "Paired devices"
    _attr_icon = "mdi:calendar-sync"

    def __init__(self, entry: ConfigEntry, runtime: dict) -> None:
        self._entry = entry
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_paired_devices"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": "Shift Plus",
            "model": "Home Assistant sync service",
        }

    @property
    def native_value(self) -> int:
        return len(self._runtime["store"].data["devices"])

    @property
    def extra_state_attributes(self) -> dict:
        store = self._runtime["store"]
        return {
            "server_cursor": store.data["cursor"],
            "stored_records": len(store.data["records"]),
            "pairing_path": f"/api/shift_plus/{self._entry.entry_id}/pairing",
        }
