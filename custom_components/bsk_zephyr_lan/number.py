import logging
from homeassistant.const import PERCENTAGE
from . import BSKZephyrConfigEntry, BSKDataUpdateCoordinator
from .entity import BSKZephyrEntity
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from dataclasses import replace

_LOGGER = logging.getLogger(__name__)

NUMBER_TYPES: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        name="Humidity Boost",
        key="humidity_boost_level",
        native_min_value=35,
        native_max_value=50,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
    ),
    NumberEntityDescription(
        name="Fan Speed",
        key="fan_speed",
        native_min_value=22,
        native_max_value=80,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fan",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BSKZephyrConfigEntry, async_add_entities
) -> None:
    for groupID, device in entry.runtime_data.coordinator.data.items():
        async_add_entities(
            BSKZephyrNumber(groupID, entry.runtime_data.coordinator, description)
            for description in NUMBER_TYPES
        )


class BSKZephyrNumber(BSKZephyrEntity, NumberEntity):
    _attr_domain = "number"
    def __init__(
        self,
        groupID: str,
        coordinator: BSKDataUpdateCoordinator,
        description: NumberEntityDescription,
    ):
        min = coordinator.api.persistent_data.get(f"{description.key}_min", None)
        if min:
            description = replace(description, native_min_value=min)
        max = coordinator.api.persistent_data.get(f"{description.key}_max", None)
        if max:
            description = replace(description, native_max_value=max)
        super().__init__(groupID, coordinator, description)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        self._attr_native_value = self.property_value

    async def async_set_native_value(self, value):
        await self.coordinator.api.control_device(
            self.groupID, **{self.entity_description.key: value}
        )
        await self.coordinator.async_status_refresh()
