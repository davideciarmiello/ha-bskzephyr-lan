from typing import Any
from . import BSKZephyrConfigEntry, BSKDataUpdateCoordinator
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

SELECT_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(name="Power", key="power"),
    SwitchEntityDescription(name="Buzzer", key="buzzer"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BSKZephyrConfigEntry, async_add_entities
) -> None:
    for groupID, device in entry.runtime_data.coordinator.data.items():
        async_add_entities(
            BSKZephyrSelect(groupID, entry.runtime_data.coordinator, description)
            for description in SELECT_TYPES
        )


class BSKZephyrSelect(SwitchEntity, CoordinatorEntity[BSKDataUpdateCoordinator]):
    def __init__(
        self,
        groupID: str,
        coordinator: BSKDataUpdateCoordinator,
        description: SwitchEntityDescription,
    ):
        super().__init__(coordinator)

        self._attr_unique_id = f"{groupID}-{description.key}"
        self._attr_name = f"{coordinator.data[groupID].group_title} {description.name}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, groupID)},
            name=coordinator.data[groupID].group_title,
            model=coordinator.data[groupID].device_model,
            sw_version=coordinator.data[groupID].device_version,
        )
        self.coordinator = coordinator
        self.groupID = groupID
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = (
            getattr(
                self.coordinator.data[self.groupID].device, self.entity_description.key
            )
        )
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._attr_is_on

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        # await self.async_write_ha_state()
        await self.set_device_power(False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        # await self.async_write_ha_state()
        await self.set_device_power(True)

    async def set_device_power(self, power: bool) -> None:
        on_off = self._attr_is_on
        await self.coordinator.api.control_device(
            self.groupID, **{self.entity_description.key: on_off}
        )
        await self.coordinator.async_request_refresh()
        # setattr(self.coordinator.data[self.groupID].settings, self.entity_description.key, on_off)
        # self.coordinator.data[self.groupID].settings.groupID = self.groupID
        # self.coordinator.data[self.groupID].settings.groupID = self.coordinator.data[self.groupID].groupID

        # await self.coordinator.api.update_group_settings(dict(self.coordinator.data[self.groupID].settings))
        # await self.coordinator.async_refresh()
