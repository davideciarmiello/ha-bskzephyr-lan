"""DataUpdateCoordinator for BSK Zephyr."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import storage
import copy

from .bsk_api import BSKZephyrLanClient, ZephyrDevice, ZephyrException

from .const import DOMAIN, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)


class BSKDataUpdateCoordinator(DataUpdateCoordinator):
    """BSK Zephyr Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: BSKZephyrLanClient,
    ) -> None:
        """Initialize data coordinator."""
        self.hass = hass
        self.entry = config_entry
        self.config = (self.entry.data or {}).copy()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=10),
        )
        self.data = {}
        self.api = client
        self.store = storage.Store(hass, version=1, key=f"{DOMAIN}.{client._raw_data["device_id"]}")
        self.store_last_saved = None
        self._async_request_refresh_from_callback = False

    async def _async_update_data(self) -> dict[str:ZephyrDevice]:
        """Request to the server to update the status from full response data."""
        from_cache = self._async_request_refresh_from_callback
        if from_cache:
            _LOGGER.debug("_async_update_data. _from_cache %s", from_cache)
        self._async_request_refresh_from_callback = False
        if not self.store_last_saved:
            self.api.persistent_data = await self.store.async_load() or {}
            self.store_last_saved = copy.deepcopy(self.api.persistent_data)
        try:
            supported_devices = await self.api.list_devices(from_cache)
            if self.api.persistent_data != self.store_last_saved:
                await self.store.async_save(self.api.persistent_data)
                self.store_last_saved = copy.deepcopy(self.api.persistent_data)
            if from_cache: #create a new request if the data is received from a callback async_status_refresh
                await self.async_request_refresh()
            return supported_devices
        except ZephyrException as e:
            raise UpdateFailed(e) from e

    async def async_status_refresh(self) -> None:
        """Refresh current status."""
        _LOGGER.debug("async_status_refresh")
        supported_devices = await self.api.list_devices(True)
        self.async_set_updated_data(supported_devices)
        self._async_request_refresh_from_callback = True
        await self.async_request_refresh()

