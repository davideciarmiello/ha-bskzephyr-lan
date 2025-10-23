from __future__ import annotations

import logging

from typing import Optional, Any, Callable

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from . import BSKZephyrConfigEntry, BSKDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class BSKZephyrEntity(CoordinatorEntity):
    """Base implementation of BSK Zephyr entities."""
    _attr_has_entity_name = True
    coordinator: BSKDataUpdateCoordinator | None = None
    device = None

    def __init__(
        self,
        groupID: str,
        coordinator: BSKDataUpdateCoordinator,
        entity_description: EntityDescription,
    ):
        super().__init__(coordinator)
        self.device = coordinator.data[groupID]
        self.coordinator = coordinator
        self.groupID = groupID
        self.entity_description = entity_description        
        if self._attr_domain is None:
            raise NotImplementedError(f"{self.__class__.__name__} must define _attr_domain")
        self._attr_unique_id = f"{DOMAIN}_{self._attr_domain}_{self.device.device_id}_{self.entity_description.key}"
        self._device_info = None  # sarà creato solo la prima volta
        self.property_value = None


    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self._handle_coordinator_update()
        await super().async_added_to_hass()

    @property
    def device_info(self):
        # Reuse the same DeviceInfo already created        
        if self._device_info is None:
            entry = self.coordinator.entry
            if not self.coordinator.data:
                return DeviceInfo(
                    identifiers={(DOMAIN, self.entry.entry_id)},
                    manufacturer="BSK",
                    name=f"BSK Zephyr LAN ({entry.data['host']})",
                    configuration_url=f"http://{entry.data['host']}"
                )
            # Creo DeviceInfo solo la prima volta
            device = self.coordinator.data[self.groupID]
            name = device.device_model            
            self._device_info = DeviceInfo(
                identifiers={(DOMAIN, device.device_id)},
                connections={(CONNECTION_NETWORK_MAC, device.device_id)},
                manufacturer="BSK",
                name=f"{device.device_name} {device.device_id}",
                model=device.device_model,
                sw_version=device.device_version,
                configuration_url=f"http://{entry.data['host']}"
            )
        return self._device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if the key exists in the data
        try:            
            return not self._get_value_from_path() is None
        except (KeyError, AttributeError):
            return False
            
    def _get_value_from_path(self) -> Any:
        """Get a value from property."""
        self.device = self.coordinator.data[self.groupID]
        value = getattr(self.device, self.entity_description.key)
        return value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.property_value = self._get_value_from_path()
        super()._handle_coordinator_update()

