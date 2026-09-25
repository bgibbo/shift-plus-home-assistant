"""UI configuration flow for Shift +."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_ROSTER_ID, CONF_UNIT_ID, DOMAIN, NAME


class ShiftPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input["name"],
                data={
                    "name": user_input["name"],
                    CONF_ROSTER_ID: "core",
                    CONF_UNIT_ID: "unit-a",
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("name", default=NAME): str}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ShiftPlusOptionsFlow()


class ShiftPlusOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        runtime = self.config_entry.runtime_data
        status = runtime.pairing_status.replace("_", " ").title()
        paired = sum(
            1
            for device in runtime.store.paired_devices.values()
            if not device.get("revoked")
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
            description_placeholders={
                "status": status,
                "paired_devices": str(paired),
            },
        )
