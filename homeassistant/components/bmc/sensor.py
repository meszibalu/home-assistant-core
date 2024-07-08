"""Platform for sensor integration."""

from __future__ import annotations

from homeassistant.components.bmc.hub import BmcHub
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry
from .devices import Devices

TEMPERATURE_ENTITY_DESCRIPTION = SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=1,
    state_class=SensorStateClass.MEASUREMENT
)

async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcSensor(hub, **config.options)])


class BmcSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, hub: BmcHub, address: int, port: int, **ignored: any) -> None:
        self._attr_unique_id = Devices.get_unique_id(address, port)
        self._attr_should_poll = False
        self.entity_description = TEMPERATURE_ENTITY_DESCRIPTION

        self._1w_port = hub.use_1w_port(address, port, self.__callback)

    def __callback(self):
        self.schedule_update_ha_state()

    @property
    def native_value(self) -> float:
        """Return the value reported by the sensor."""
        return self._1w_port.read()

    async def async_will_remove_from_hass(self) -> None:
        self._1w_port.release()
