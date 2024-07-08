"""Platform for light integration."""

from __future__ import annotations

from functools import cached_property
from typing import Any

from homeassistant.components.bmc.hub import BmcHub
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry
from .devices import Devices

ONOFF_COLOR_MODES = {ColorMode.ONOFF}
PWM_COLOR_MODES = {ColorMode.BRIGHTNESS}

async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the Bali Muvek Light platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcLight(hub, **config.options)])

class BmcLight(LightEntity):
    """Representation of a Bali Muvek Light."""

    def __init__(self, hub: BmcHub, address: int, output: int, pwm: bool, invert: bool,
                 **ignored: any) -> None:
        """Initialize a BmcLight."""

        self._attr_unique_id = Devices.get_unique_id(address, output)
        self._attr_should_poll = False
        self._pwm = pwm

        self._io_output = hub.use_io_output(address, output, pwm, invert)
        self._write(0)

    @cached_property
    def color_mode(self) -> ColorMode:
        if self._pwm:
            return ColorMode.BRIGHTNESS
        else:
            return ColorMode.ONOFF

    @cached_property
    def supported_color_modes(self) -> set[ColorMode]:
        if self._pwm:
            return PWM_COLOR_MODES
        else:
            return ONOFF_COLOR_MODES

    @property
    def brightness(self):
        """Return the brightness of the light."""

        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""

        return self._brightness > 0

    def _write(self, brightness: int) -> None:
        self._io_output.write(brightness)
        self._brightness = brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""

        if self._pwm:
            self._write(kwargs.get(ATTR_BRIGHTNESS, 255))
        else:
            self._write(255)

        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        self._write(0)
        self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await self.async_turn_off()

        self._io_output.release()
