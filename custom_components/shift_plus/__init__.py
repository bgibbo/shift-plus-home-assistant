"""Shift Plus Home Assistant integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import persistent_notification
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.network import get_url

from .api import VIEWS
from .const import DOMAIN, PLATFORMS
from .store import ShiftPlusStore


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register API views once."""
    hass.data.setdefault(DOMAIN, {})
    frontend_path = Path(__file__).parent / "frontend" / "shift-plus-roster-card.js"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/shift_plus/shift-plus-roster-card.js",
                str(frontend_path),
                cache_headers=True,
            )
        ]
    )
    for view in VIEWS:
        hass.http.register_view(view)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load one Shift Plus synchronization instance."""
    store = ShiftPlusStore(hass, entry.entry_id)
    await store.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "entry": entry,
        "store": store,
    }

    async def create_pairing(call: ServiceCall) -> None:
        base_url = get_url(hass, prefer_external=False).rstrip("/")
        pairing_url = f"{base_url}/api/shift_plus/{entry.entry_id}/pairing"
        persistent_notification.async_create(
            hass,
            f"Open [{pairing_url}]({pairing_url}) while signed in to Home Assistant, "
            "then scan the displayed QR in Shift +. "
            "The QR expires after five minutes.",
            title="Pair Shift +",
            notification_id=f"shift_plus_pairing_{entry.entry_id}",
        )

    hass.services.async_register(DOMAIN, "create_pairing", create_pairing)
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Shift Plus."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.services.async_remove(DOMAIN, "create_pairing")
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
