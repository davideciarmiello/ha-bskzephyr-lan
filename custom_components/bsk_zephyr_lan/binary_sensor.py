from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
    BinarySensorEntityDescription
)
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import logging
from . import BSKZephyrConfigEntry
from .coordinator import BSKDataUpdateCoordinator
from .entity import BSKZephyrEntity


_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        name="Humidity Boost Running",
        key="humidity_boost_running",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BSKZephyrConfigEntry, async_add_entities
) -> None:
    for groupID, device in entry.runtime_data.coordinator.data.items():
        async_add_entities(
            BSKZephyrBinarySensor(groupID, entry.runtime_data.coordinator, description)
            for description in BINARY_SENSOR_TYPES
        )


class BSKZephyrBinarySensor(BSKZephyrEntity, BinarySensorEntity):
    _attr_domain = "binary_sensor"
    def __init__(self, groupID: str, coordinator: BSKDataUpdateCoordinator, description: BinarySensorEntityDescription):
        super().__init__(groupID, coordinator, description)

    @property
    def is_on(self):
        return bool(self.property_value)