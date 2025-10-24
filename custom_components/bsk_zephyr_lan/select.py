import logging

from . import BSKZephyrConfigEntry, BSKDataUpdateCoordinator
from .entity import BSKZephyrEntity
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError

from .bsk_api import FanMode, FanSpeed

_LOGGER = logging.getLogger(__name__)

SELECT_TYPES: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        name="Fan Mode", key="operation_mode_enum", options=[m.name for m in FanMode]
    ),
    SelectEntityDescription(
        name="Fan Speed", key="fan_speed_enum", options=[s.name for s in FanSpeed]
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BSKZephyrConfigEntry, async_add_entities
) -> None:
    for groupID, device in entry.runtime_data.coordinator.data.items():
        async_add_entities(
            BSKZephyrSelect(groupID, entry.runtime_data.coordinator, description)
            for description in SELECT_TYPES
        )


class BSKZephyrSelect(BSKZephyrEntity, SelectEntity):
    _attr_domain = "select"
    def __init__(
        self,
        groupID: str,
        coordinator: BSKDataUpdateCoordinator,
        description: SelectEntityDescription,
    ):
        super().__init__(groupID, coordinator, description)

    @property
    def state(self):
        return self.property_value.name

    async def async_select_option(self, option: str) -> None:
        if option == self.state:
            return  # niente da fare se è già selezionato
        await self.coordinator.api.control_device(
            self.groupID, **{self.entity_description.key: option}
        )
        await self.coordinator.async_status_refresh()
