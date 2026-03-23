"""Platform for binary sensor integration.

A binary sensor is connected to an I/O Input and it publishes the input
actual state.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BmhConfigEntry
from .hub import BmhHub
from .strings import Strings

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: BmhConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create binary sensor entity."""

    entity = await __async_create(hass, **config.options)
    add_entities([entity])


async def __async_create(
    hass: HomeAssistant,
    device_class: str,
    address: int,
    input: int,
    invert: bool,
    **ignored: Any,
) -> BmhBinarySensor:
    hub = await BmhHub.async_get(hass)

    return BmhBinarySensor(hub, device_class, address, input, invert)


class BmhBinarySensor(BinarySensorEntity):
    """Representation of a binary sensor."""

    def __init__(
        self, hub: BmhHub, device_class: str, address: int, input: int, invert: bool
    ) -> None:
        """Initialize a new binary sensor."""

        self._attr_unique_id = Strings.get_unique_id(address, input)
        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning("Unknown device class '%s'", device_class)

        self._io_input = hub.create_io_input(
            address, input, invert, self.__on_change, self.__on_error
        )

    async def async_added_to_hass(self) -> None:
        """Open the binary sensor."""

        await self._io_input.async_open()

        self._io_input.read()

    async def async_will_remove_from_hass(self) -> None:
        """Remove binary sensor from hass and release it."""

        await self._io_input.async_release()

    def __on_change(self, value: bool) -> None:
        self._attr_is_on = value
        self.schedule_update_ha_state()

    def __on_error(self, error: Exception) -> None:
        self._io_input.log_error(error)

        self._attr_is_on = None
        self.schedule_update_ha_state()
