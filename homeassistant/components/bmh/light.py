"""Platform for light integration.

A light is connected to an I/O Output and it can be switched on or off.
It supports brightness setting by PWM.
"""

from __future__ import annotations

from typing import Any

from propcache.api import cached_property

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BmhConfigEntry
from .hub import BmhHub
from .strings import Strings

ONOFF_COLOR_MODES = {ColorMode.ONOFF}
PWM_COLOR_MODES = {ColorMode.BRIGHTNESS}


async def async_setup_entry(
    hass: HomeAssistant,
    config: BmhConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create light entity."""

    entity = await __async_create(hass, **config.options)
    add_entities([entity])


async def __async_create(
    hass: HomeAssistant,
    address: int,
    output: int,
    pwm: bool,
    invert: bool,
    **ignored: Any,
) -> BmhLight:
    hub = await BmhHub.async_get(hass)

    return BmhLight(hub, address, output, pwm, invert)


class BmhLight(LightEntity):
    """Representation of a light."""

    def __init__(
        self, hub: BmhHub, address: int, output: int, pwm: bool, invert: bool
    ) -> None:
        """Initialize a new light."""

        self._attr_unique_id = Strings.get_unique_id(address, output)
        self._attr_should_poll = False

        self._io_output = hub.create_io_output(
            address, output, pwm, invert, self.__on_change, self.__on_error
        )

    async def async_added_to_hass(self) -> None:
        """Open the light."""

        await self._io_output.async_open()

        self._io_output.read()
        await self.async_turn_off()

    async def async_will_remove_from_hass(self) -> None:
        """Turn off the light and release it."""

        await self.async_turn_off()
        await self._io_output.async_release()

    def __on_change(self, value: int) -> None:
        self._attr_brightness = value
        self.schedule_update_ha_state()

    def __on_error(self, error: Exception) -> None:
        self._io_output.log_error(error)

        self._attr_brightness = None
        self.schedule_update_ha_state()

    @cached_property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light. It can be ONOFF or BRIGHTNESS."""

        if self._io_output.pwm:
            return ColorMode.BRIGHTNESS

        return ColorMode.ONOFF

    @cached_property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color mode of the light."""

        if self._io_output.pwm:
            return PWM_COLOR_MODES

        return ONOFF_COLOR_MODES

    @property
    def brightness(self):
        """Return the brightness of the light."""

        return self._attr_brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""

        if self._attr_brightness is None:
            return None

        return self._attr_brightness > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""

        if self._io_output.pwm:
            await self._io_output.async_on(kwargs.get(ATTR_BRIGHTNESS, 255))
        else:
            await self._io_output.async_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        await self._io_output.async_off()
