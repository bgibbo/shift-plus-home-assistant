"""Config flow for Shift Plus."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ENTITLEMENT_PUBLIC_KEY, CONF_NAME, DOMAIN, NAME


class ShiftPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a Shift Plus integration instance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial configuration."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ENTITLEMENT_PUBLIC_KEY: user_input.get(
                        CONF_ENTITLEMENT_PUBLIC_KEY, ""
                    ).strip(),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=NAME): str,
                    vol.Optional(CONF_ENTITLEMENT_PUBLIC_KEY, default=""): str,
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ShiftPlusOptionsFlow:
        """Return the options flow."""
        return ShiftPlusOptionsFlow(config_entry)


class ShiftPlusOptionsFlow(config_entries.OptionsFlow):
    """Configure Shift Plus options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update the entitlement verification key."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.options.get(
            CONF_ENTITLEMENT_PUBLIC_KEY,
            self._entry.data.get(CONF_ENTITLEMENT_PUBLIC_KEY, ""),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_ENTITLEMENT_PUBLIC_KEY, default=current): str}
            ),
        )
