"""Platform for sensor integration.

A sensor is connected to a 1-Wire Port and publishes the temperature of
connected DS18B20 sensors.
"""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BmhConfigEntry
from .hub import BmhHub
from .strings import Strings

TEMPERATURE_ENTITY_DESCRIPTION = SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=1,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config: BmhConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensor entity."""

    entity = await __async_create(hass, **config.options)
    add_entities([entity])


async def __async_create(
    hass: HomeAssistant, address: int, port: int, **ignored: Any
) -> BmhSensor:
    hub = await BmhHub.async_get(hass)

    return BmhSensor(hub, address, port)


class BmhSensor(SensorEntity):
    """Representation of a sensor."""

    def __init__(self, hub: BmhHub, address: int, port: int) -> None:
        """Initialize a new sensor."""

        self._attr_unique_id = Strings.get_unique_id(address, port)
        self._attr_should_poll = False

        self.entity_description = TEMPERATURE_ENTITY_DESCRIPTION

        self._1w_port = hub.create_1w_port(
            address, port, self.__on_change, self.__on_error
        )

    async def async_added_to_hass(self) -> None:
        """Open the sensor."""

        await self._1w_port.async_open()

        self._1w_port.read()

    async def async_will_remove_from_hass(self) -> None:
        """Remove sensor from hass and release it."""

        await self._1w_port.async_release()

    def __on_change(self, value: float | None) -> None:
        if value is not None and math.isnan(value):
            self.__on_error(ValueError("Invalid temperature value"))
            return

        self._attr_native_value = value
        self.schedule_update_ha_state()

    def __on_error(self, error: Exception) -> None:
        self._1w_port.log_error(error)

        self._attr_native_value = None
        self.schedule_update_ha_state()
