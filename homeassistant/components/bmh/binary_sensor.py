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

    entity = BmhBinarySensor(device_class)
    await entity.async_init(hub, address, input, invert)

    return entity


class BmhBinarySensor(BinarySensorEntity):
    """Representation of a binary sensor."""

    def __init__(self, device_class: str) -> None:
        """Initialize a new binary sensor.

        async_init() is required to finish I/O initialization.
        """

        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning("Unknown device class '%s'", device_class)

    async def async_init(
        self, hub: BmhHub, address: int, input: int, invert: bool
    ) -> None:
        """Finish initialization and open I/O."""

        self._attr_unique_id = Strings.get_unique_id(address, input)

        # pylint: disable=attribute-defined-outside-init
        self._io_input = await hub.async_open_io_input(
            address, input, invert, self.__on_change
        )

        self._io_input.read()

    def __on_change(self, value: bool) -> None:
        self._attr_is_on = value
        self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Remove binary sensor from hass and release it."""

        await self._io_input.async_release()
