"""DataUpdateCoordinator for BSK Zephyr."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.bsk_api import BSKZephyrLanClient, Zephyr, ZephyrException

from .const import DOMAIN, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)


class BSKDataUpdateCoordinator(DataUpdateCoordinator[list[Zephyr]]):
    """BSK Zephyr Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
        client: BSKZephyrLanClient,
    ) -> None:
        """Initialize data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=10),
            always_update=False,
        )

        self.data = {}
        self.api = client

    async def _async_update_data(self) -> dict[str:Zephyr]:
        """Request to the server to update the status from full response data."""
        try:
            device_list = await self.api.list_devices()
            supported_devices = {}
            for device in device_list:
                supported_devices[device.groupID] = device
            return supported_devices
        except ZephyrException as e:
            raise UpdateFailed(e) from e

    # def refresh_status(self) -> None:
    #     """Refresh current status."""
    #     self.async_set_updated_data(self.data)


async def async_setup_device_coordinator(
    hass: HomeAssistant, config_entry, client: BSKZephyrLanClient
) -> BSKDataUpdateCoordinator:
    """Create DeviceDataUpdateCoordinator and device_api per device."""
    coordinator = BSKDataUpdateCoordinator(hass, config_entry, client)
    await coordinator.async_refresh()

    _LOGGER.debug(
        "Setup device's coordinator",
    )
    return coordinator
