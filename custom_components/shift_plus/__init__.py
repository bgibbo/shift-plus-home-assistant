"""Shift + standalone and paired Home Assistant integration."""

from __future__ import annotations

import uuid

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .api import register_views
from .const import (
    DOMAIN,
    ENTITLEMENT_PUBLIC_KEY,
    PLATFORMS,
    SERVICE_ADD_LEAVE,
    SERVICE_ADD_OVERTIME,
    SERVICE_DELETE_LEAVE,
    SERVICE_DELETE_OVERTIME,
    SERVICE_RESOLVE_CONFLICT,
    SERVICE_SET_ACTIVE_SCHEDULE,
    SERVICE_SYNC_NOW,
    SERVICE_UPDATE_LEAVE,
    SERVICE_UPDATE_OVERTIME,
)
from .coordinator import RuntimeData, ShiftPlusCoordinator
from .security import EntitlementVerifier, PairingManager
from .storage import ShiftPlusStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    if not hass.data[DOMAIN].get("views_registered"):
        register_views(hass)
        hass.data[DOMAIN]["views_registered"] = True
        _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _migrate_pairing_status_entity(hass, entry)
    store = ShiftPlusStore(hass, entry.entry_id)
    await store.async_load()
    coordinator = ShiftPlusCoordinator(hass, entry, store)
    pairing = PairingManager(
        entry.entry_id, EntitlementVerifier(ENTITLEMENT_PUBLIC_KEY)
    )
    runtime = RuntimeData(coordinator=coordinator, store=store, pairing=pairing)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    entry.runtime_data = runtime
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


def _migrate_pairing_status_entity(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate beta pairing-status IDs instead of leaving orphan entities."""
    registry = er.async_get(hass)
    current_unique_id = f"{entry.entry_id}_android_pairing_status"
    current_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, current_unique_id
    )
    for legacy_unique_id in (
        f"{entry.entry_id}_pairing_status",
        f"{entry.entry_id}_android_pairing",
    ):
        legacy_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, legacy_unique_id
        )
        if legacy_entity_id is None:
            continue
        if current_entity_id is None:
            registry.async_update_entity(
                legacy_entity_id, new_unique_id=current_unique_id
            )
            current_entity_id = legacy_entity_id
        else:
            registry.async_remove(legacy_entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _entry_runtime(hass: HomeAssistant):
    entries = [
        value for key, value in hass.data[DOMAIN].items() if key != "views_registered"
    ]
    if len(entries) != 1:
        raise ValueError("Shift + requires exactly one configured entry")
    return entries[0]


def _register_services(hass: HomeAssistant) -> None:
    async def add_overtime(call: ServiceCall) -> None:
        runtime = _entry_runtime(hass)
        record_id = call.data.get("id") or str(uuid.uuid4())
        day = cv.date(call.data["date"]).isoformat()
        existing = next(
            (item for item in runtime.store.records("overtime") if item["date"] == day),
            None,
        )
        if existing and existing["id"] != record_id:
            raise ValueError(
                "Only one manually entered overtime record per date is supported"
            )
        await runtime.store.async_upsert(
            "overtime",
            record_id,
            {
                "date": day,
                "start_minutes": int(call.data["start_minutes"]),
                "finish_minutes": int(call.data["finish_minutes"]),
                "description": call.data.get("description"),
            },
        )
        await runtime.coordinator.async_request_refresh()

    async def delete_overtime(call: ServiceCall) -> None:
        runtime = _entry_runtime(hass)
        await runtime.store.async_delete("overtime", call.data["id"])
        await runtime.coordinator.async_request_refresh()

    async def add_leave(call: ServiceCall) -> None:
        runtime = _entry_runtime(hass)
        record_id = call.data.get("id") or str(uuid.uuid4())
        await runtime.store.async_upsert(
            "annual_leave",
            record_id,
            {
                "start_date": cv.date(call.data["start_date"]).isoformat(),
                "number_of_days": int(call.data["number_of_days"]),
                "day_portion": call.data.get("day_portion", "fullDay"),
            },
        )
        await runtime.coordinator.async_request_refresh()

    async def delete_leave(call: ServiceCall) -> None:
        runtime = _entry_runtime(hass)
        await runtime.store.async_delete("annual_leave", call.data["id"])
        await runtime.coordinator.async_request_refresh()

    async def sync_now(call: ServiceCall) -> None:
        runtime = _entry_runtime(hass)
        if not any(
            not device.get("revoked")
            for device in runtime.store.paired_devices.values()
        ):
            raise HomeAssistantError("No Android device is paired")
        await runtime.coordinator.async_request_refresh()

    async def resolve_conflict(call: ServiceCall) -> None:
        runtime = _entry_runtime(hass)
        try:
            await runtime.store.async_resolve_conflict(
                call.data["conflict_id"], call.data["selection"]
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await runtime.coordinator.async_request_refresh()
        runtime.coordinator.async_update_listeners()

    async def set_active_schedule(call: ServiceCall) -> None:
        runtime = _entry_runtime(hass)
        roster_id = call.data["roster_id"]
        unit_id = call.data["unit_id"]
        if unit_id not in runtime.coordinator.engine.unit_ids(roster_id):
            raise ValueError("Unit is not available for the selected roster")
        await runtime.store.async_upsert(
            "active_configuration",
            "active",
            {
                "organisation_name": call.data.get("organisation_name", "Garda"),
                "active_roster_id": roster_id,
                "active_unit_id": unit_id,
                "include_tour_briefing": bool(
                    call.data.get("include_tour_briefing", False)
                ),
                "roster_schedule_settings": {},
            },
        )
        await runtime.coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_ADD_OVERTIME, add_overtime)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_OVERTIME, add_overtime)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_OVERTIME, delete_overtime)
    hass.services.async_register(DOMAIN, SERVICE_ADD_LEAVE, add_leave)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_LEAVE, add_leave)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_LEAVE, delete_leave)
    hass.services.async_register(DOMAIN, SERVICE_SYNC_NOW, sync_now)
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESOLVE_CONFLICT,
        resolve_conflict,
        schema=vol.Schema(
            {
                vol.Required("conflict_id"): cv.string,
                vol.Required("selection"): vol.In(("current", "alternative")),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ACTIVE_SCHEDULE, set_active_schedule
    )
