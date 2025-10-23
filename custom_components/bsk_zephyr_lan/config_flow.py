"""Config flow for the BSK Zephyr integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bsk_api import BSKZephyrLanClient, InvalidAuthError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str
    }
)


class SetupBSKZephyrLanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BSK Zephyr."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:

            try:
                client = BSKZephyrLanClient(
                    async_get_clientsession(self.hass),
                    user_input[CONF_HOST],
                )
                await client.login()
            except InvalidAuthError as e:
                errors["base"] = str(e)
            except Exception as e:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = str(e)
            else:                
                await self.async_set_unique_id(client._raw_data["device_id"])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=user_input[CONF_HOST] + " " + client._raw_data["device_id"], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
