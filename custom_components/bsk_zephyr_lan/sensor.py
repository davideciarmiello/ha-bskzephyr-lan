import logging
from . import BSKZephyrConfigEntry
from .coordinator import BSKDataUpdateCoordinator
from .entity import BSKZephyrEntity
from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError


_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="Temperature",
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        name="Humidity",
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        name="Filter Status",
        key="filter_timer",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
    SensorEntityDescription(
        name="Capsule Status",
        key="hygiene_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cylinder",
    ),
    SensorEntityDescription(
        name="Wi-Fi SSID",
        key="wifi_ssid",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        name="Wi-Fi RSSI",
        key="wifi_rssi",
        native_unit_of_measurement="dBm",
        #icon="mdi:wifi-strength-3",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        name="Wi-Fi IP",
        key="wifi_ip",
        icon="mdi:ip",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BSKZephyrConfigEntry, async_add_entities
) -> None:
    for groupID, device in entry.runtime_data.coordinator.data.items():
        async_add_entities(
            BSKZephyrSensor(groupID, entry.runtime_data.coordinator, description)
            for description in SENSOR_TYPES
        )


class BSKZephyrSensor(BSKZephyrEntity, SensorEntity):
    _attr_domain = "sensor"
    def __init__(self, groupID: str, coordinator: BSKDataUpdateCoordinator, description: SensorEntityDescription):
        super().__init__(groupID, coordinator, description)

    @property
    def state(self):
        return self.property_value
