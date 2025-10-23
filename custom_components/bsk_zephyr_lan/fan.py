import logging
import math
from typing import List, Tuple, Optional, Any
from homeassistant.const import PERCENTAGE
from . import BSKZephyrConfigEntry, BSKDataUpdateCoordinator
from .entity import BSKZephyrEntity
from homeassistant.components.fan import (FanEntity, FanEntityDescription, FanEntityFeature, 
    DIRECTION_FORWARD,
    DIRECTION_REVERSE)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import ranged_value_to_percentage, percentage_to_ranged_value
from homeassistant.util.scaling import int_states_in_range

from .bsk_api import FanMode, FanSpeed

_LOGGER = logging.getLogger(__name__)

FAN_DESCRIPTION = FanEntityDescription(name="Fan", key="fan_speed")

async def async_setup_entry(
    hass: HomeAssistant, entry: BSKZephyrConfigEntry, async_add_entities
) -> None:
    for groupID, device in entry.runtime_data.coordinator.data.items():
        async_add_entities([BSKZephyrFan(groupID, entry.runtime_data.coordinator, FAN_DESCRIPTION)])


class BSKZephyrFan(BSKZephyrEntity, FanEntity):
    _attr_domain = "fan"
    
    SPEED_RANGE = (22, 80)

    def __init__(
        self,
        groupID: str,
        coordinator: BSKDataUpdateCoordinator,
        description: FanEntityDescription,
    ):
        super().__init__(groupID, coordinator, description)
        self._attr_supported_features = (FanEntityFeature.SET_SPEED | FanEntityFeature.DIRECTION | FanEntityFeature.PRESET_MODE | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF)

    @property
    def is_on(self):
        return self.device.power

    @property
    def current_direction(self):
        """Return the current direction."""
        if self.device.operation_mode_enum == FanMode.Supply:
            return DIRECTION_FORWARD
        if self.device.operation_mode_enum == FanMode.Extract:
            return DIRECTION_REVERSE
        return self.device.operation_mode_enum.name

    #for now is not supported!
    @property
    def direction_list(self):
        """Return the list of supported directions."""
        return [m.name for m in FanMode]

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        if direction == self.current_direction:
            return
        if direction == DIRECTION_FORWARD:
            direction = FanMode.Supply.name
        if direction == DIRECTION_REVERSE:
            direction = FanMode.Extract.name
        if self.direction_list is None or direction not in self.direction_list:
            raise ValueError(f"{direction} is not a valid direction_mode: {self.direction_list}")
        new_state = (self.device.operation_mode_enum.__class__)[direction]
        await self.coordinator.api.control_device(self.groupID, operation_mode_enum=new_state)
        await self.coordinator.async_status_refresh()


    @property
    def preset_mode(self):
        return self.device.fan_speed_enum.name

    @property
    def preset_modes(self):
        return [m.name for m in FanSpeed]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the speed of the fan asynchronously."""        
        if preset_mode == self.preset_mode:
            return
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            raise ValueError(f"{preset_mode} is not a valid preset_mode: {self.preset_modes}")
        new_state = (self.device.fan_speed_enum.__class__)[preset_mode]
        await self.coordinator.api.control_device(self.groupID, fan_speed_enum=new_state)
        await self.coordinator.async_status_refresh()


    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        return ranged_value_to_percentage(self.SPEED_RANGE, self.device.fan_speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self.SPEED_RANGE)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == self.percentage:
            return
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self.device.power:
            await self.coordinator.api.control_device(self.groupID, power=True)
        new_state = int(math.ceil(percentage_to_ranged_value(self.SPEED_RANGE, percentage)))
        await self.coordinator.api.control_device(self.groupID, fan_speed=new_state)
        await self.coordinator.async_status_refresh()

    async def async_turn_on(self, 
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs) -> None:
        """Turn on the fan asynchronously."""
        if not self.device.power:
            await self.coordinator.api.control_device(self.groupID, power=True)
            await self.coordinator.async_status_refresh()
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        if percentage is not None:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan asynchronously."""
        if not self.device.power:
            return
        await self.coordinator.api.control_device(self.groupID, power=False)
        await self.coordinator.async_status_refresh()
        