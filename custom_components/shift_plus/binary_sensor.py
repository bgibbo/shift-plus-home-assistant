"""Shift + working-state binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .coordinator import RuntimeData
from .entity import ShiftPlusEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(key="working_now", name="Working now"),
    BinarySensorEntityDescription(key="working_today", name="Working today"),
    BinarySensorEntityDescription(key="working_tomorrow", name="Working tomorrow"),
    BinarySensorEntityDescription(key="annual_leave_today", name="Annual leave today"),
    BinarySensorEntityDescription(key="overtime_today", name="Overtime today"),
    BinarySensorEntityDescription(
        key="paired", name="Android app paired", entity_registry_enabled_default=False
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities([ShiftPlusBinarySensor(runtime, item) for item in DESCRIPTIONS])


class ShiftPlusBinarySensor(ShiftPlusEntity, BinarySensorEntity):
    def __init__(
        self, runtime: RuntimeData, description: BinarySensorEntityDescription
    ) -> None:
        super().__init__(runtime.coordinator, description.key)
        self.runtime = runtime
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return {
            "working_now": data["working_now"],
            "working_today": data["duty"].working,
            "working_tomorrow": data["tomorrow"].working,
            "annual_leave_today": data["leave_today"] is not None,
            "overtime_today": data["overtime_today"] is not None,
            "paired": any(
                not item.get("revoked")
                for item in self.runtime.store.paired_devices.values()
            ),
        }[self.entity_description.key]
