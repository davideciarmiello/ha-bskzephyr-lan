import logging
from typing import Any
from . import BSKZephyrConfigEntry, BSKDataUpdateCoordinator
from .entity import BSKZephyrEntity
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(name="Power", key="power"),
    SwitchEntityDescription(name="Buzzer", key="buzzer"),
    SwitchEntityDescription(name="Humidity Boost", key="humidity_boost_enabled"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BSKZephyrConfigEntry, async_add_entities
) -> None:
    for groupID, device in entry.runtime_data.coordinator.data.items():
        async_add_entities(
            BSKZephyrSwitch(groupID, entry.runtime_data.coordinator, description)
            for description in SWITCH_TYPES
        )


class BSKZephyrSwitch(BSKZephyrEntity, SwitchEntity):
    _attr_domain = "switch"
    def __init__(
        self,
        groupID: str,
        coordinator: BSKDataUpdateCoordinator,
        description: SwitchEntityDescription,
    ):
        super().__init__(groupID, coordinator, description)

    @property
    def is_on(self):
        return self.property_value

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.set_device_on_off(False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.set_device_on_off(True)

    async def set_device_on_off(self, state: bool) -> None:
        await self.coordinator.api.control_device(
            self.groupID, **{self.entity_description.key: state}
        )
        await self.coordinator.async_status_refresh()
