"""Frontend resource registration for the Shift + roster card."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
FRONTEND_RESOURCE_URL = f"/{DOMAIN}/shift-plus-roster-card.js"
_FRONTEND_RESOURCE = {"url": FRONTEND_RESOURCE_URL, "res_type": "module"}


async def async_setup_frontend(hass: Any) -> None:
    """Serve the card and register it with storage-mode Lovelace dashboards."""
    path = Path(__file__).parent / "frontend" / "shift-plus-roster-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_RESOURCE_URL, str(path), cache_headers=False)]
    )
    async_at_started(hass, async_ensure_lovelace_resource)


async def async_ensure_lovelace_resource(hass: Any) -> None:
    """Register one module resource when Lovelace uses storage mode."""
    lovelace = hass.data.get("lovelace")
    resources = lovelace.get("resources") if isinstance(lovelace, dict) else None
    if resources is None or not hasattr(resources, "async_create_item"):
        _LOGGER.info(
            "Shift + roster card is served at %s; add it to YAML Lovelace resources "
            "if you use a YAML dashboard",
            FRONTEND_RESOURCE_URL,
        )
        return
    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True
    existing = next(
        (
            item
            for item in resources.async_items()
            if item.get("url", "").split("?", 1)[0] == FRONTEND_RESOURCE_URL
        ),
        None,
    )
    if existing is None:
        existing = await resources.async_create_item(_FRONTEND_RESOURCE)
        hass.data[DOMAIN]["frontend_resource_id"] = existing.get("id")


async def async_remove_frontend_resource(hass: Any) -> None:
    """Remove only the resource this integration created on final unload."""
    resource_id = hass.data.get(DOMAIN, {}).pop("frontend_resource_id", None)
    lovelace = hass.data.get("lovelace")
    resources = lovelace.get("resources") if isinstance(lovelace, dict) else None
    if (
        resource_id
        and resources is not None
        and hasattr(resources, "async_delete_item")
    ):
        await resources.async_delete_item(resource_id)
