"""Platform for switch integration.

A switch is connected to an I/O Output and it can be switched on or off.
Home Assistant switches do not support PWM.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BmhConfigEntry
from .hub import BmhHub
from .strings import Strings


async def async_setup_entry(
    hass: HomeAssistant,
    config: BmhConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create switch entity."""

    entity = await __async_create(hass, **config.options)
    add_entities([entity])


async def __async_create(
    hass: HomeAssistant, address: int, output: int, invert: bool, **ignored: Any
) -> BmhSwitch:
    hub = await BmhHub.async_get(hass)

    return BmhSwitch(hub, address, output, invert)


class BmhSwitch(SwitchEntity):
    """Representation of a switch."""

    def __init__(self, hub: BmhHub, address: int, output: int, invert: bool) -> None:
        """Initialize a new switch."""

        self._attr_unique_id = Strings.get_unique_id(address, output)
        self._attr_should_poll = False

        self._io_output = hub.create_io_output(
            address, output, False, invert, self.__on_change, self.__on_error
        )

    async def async_added_to_hass(self) -> None:
        """Open the switch."""

        await self._io_output.async_open()

        self._io_output.read()
        await self.async_turn_off()

    async def async_will_remove_from_hass(self) -> None:
        """Remove switch from hass and release it."""

        await self.async_turn_off()
        await self._io_output.async_release()

    def __on_change(self, value: int) -> None:
        self._attr_is_on = value != 0
        self.schedule_update_ha_state()

    def __on_error(self, error: Exception) -> None:
        self._io_output.log_error(error)

        self._attr_is_on = None
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""

        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""

        await self._io_output.async_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""

        await self._io_output.async_off()
