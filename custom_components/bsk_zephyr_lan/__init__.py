"""The BSK Zephyr integration."""

from __future__ import annotations
from dataclasses import dataclass

import logging

from .coordinator import BSKDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bsk_api import BSKZephyrLanClient, InvalidAuthError
from homeassistant.exceptions import ConfigEntryAuthFailed

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass(kw_only=True)
class BSKZephyrData:
    coordinator: BSKDataUpdateCoordinator


type BSKZephyrConfigEntry = ConfigEntry[BSKZephyrData]  # noqa: F821


async def async_setup_entry(hass: HomeAssistant, entry: BSKZephyrConfigEntry) -> bool:
    """Set up BSK Zephyr from a config entry."""

    client = BSKZephyrLanClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
    )

    try:
        await client.login()
    except InvalidAuthError as err:
        raise ConfigEntryAuthFailed("Credentials error from BSK Zephyr") from err

    coordinator = BSKDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.debug("Setup device's coordinator")

    entry.runtime_data = BSKZephyrData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: BSKZephyrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)
