"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.bmc.hub import BmcHub
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry
from .devices import Devices
from ..binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcBinarySensor(hub, **config.options)])

class BmcBinarySensor(BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, hub: BmcHub, address: int, input: int, device_class: str, invert: bool,
                 **ignored: any) -> None:
        self._attr_unique_id = Devices.get_unique_id(address, input)
        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning(f"Unknown device class '{device_class}.")

        self._io_input = hub.use_io_input(address, input, invert, self.__callback)

    def __callback(self):
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._io_input.read()

    async def async_will_remove_from_hass(self) -> None:
        self._io_input.release()
