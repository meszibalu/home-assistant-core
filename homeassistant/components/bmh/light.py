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

    entity = BmhLight()
    await entity.async_init(hub, address, output, pwm, invert)

    return entity


class BmhLight(LightEntity):
    """Representation of a light."""

    def __init__(self) -> None:
        """Initialize a new light.

        async_init() is required to finish I/O initialization.
        """

        self._attr_should_poll = False

        self._brightness = 0

    async def async_init(
        self, hub: BmhHub, address: int, output: int, pwm: bool, invert: bool
    ) -> None:
        """Finish initialization and open I/O."""

        self._attr_unique_id = Strings.get_unique_id(address, output)

        # pylint: disable=attribute-defined-outside-init
        self._pwm = pwm

        self._io_output = await hub.async_open_io_output(
            address, output, pwm, invert, self.__on_change
        )

        self._io_output.read()
        await self._io_output.async_off()

    @cached_property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light. It can be ONOFF or BRIGHTNESS."""
        if self._pwm:
            return ColorMode.BRIGHTNESS

        return ColorMode.ONOFF

    @cached_property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color mode of the light."""
        if self._pwm:
            return PWM_COLOR_MODES

        return ONOFF_COLOR_MODES

    @property
    def brightness(self):
        """Return the brightness of the light."""

        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""

        return self._brightness > 0

    def __on_change(self, value: int) -> None:
        self._brightness = value
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""

        if self._pwm:
            await self._io_output.async_on(kwargs.get(ATTR_BRIGHTNESS, 255))
        else:
            await self._io_output.async_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        await self._io_output.async_off()

    async def async_will_remove_from_hass(self) -> None:
        """Remove light from hass and release it."""

        await self.async_turn_off()
        await self._io_output.async_release()
