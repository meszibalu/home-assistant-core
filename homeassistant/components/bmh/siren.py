"""Platform for siren integration.

A siren is connected to an I/O Output and it can be switched on or off.
It supports duration (switching on for a certain amount of time) and
volume level by PWM.
"""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BmhConfigEntry
from .async_sequencer import AsyncSequencer
from .hub import BmhHub
from .strings import Strings


async def async_setup_entry(
    hass: HomeAssistant,
    config: BmhConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create siren entity."""

    entity = await __async_create(hass, **config.options)
    add_entities([entity])


async def __async_create(
    hass: HomeAssistant,
    address: int,
    output: int,
    pwm: bool,
    invert: bool,
    **ignored: Any,
) -> BmhSiren:
    hub = await BmhHub.async_get(hass)

    entity = BmhSiren()
    await entity.async_init(hub, address, output, pwm, invert)

    return entity


class BmhSiren(SirenEntity):
    """Representation of a siren."""

    def __init__(self) -> None:
        """Initialize a new siren.

        async_init() is required to finish I/O initialization.
        """

        self._attr_should_poll = False

        self._on = False

    async def async_init(
        self, hub: BmhHub, address: int, output: int, pwm: bool, invert: bool
    ) -> None:
        """Finish initialization and open I/O."""

        self._attr_unique_id = Strings.get_unique_id(address, output)

        if pwm:
            volume_feature = SirenEntityFeature.VOLUME_SET
        else:
            volume_feature = SirenEntityFeature(0)

        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON
            | SirenEntityFeature.TURN_OFF
            | SirenEntityFeature.DURATION
            | volume_feature
        )

        # pylint: disable=attribute-defined-outside-init
        self._lock = asyncio.Lock()
        self._sequencer = AsyncSequencer(hub.loop)

        self._io_output = await hub.async_open_io_output(
            address, output, pwm, invert, self.__on_change
        )

        self._io_output.read()
        await self._io_output.async_off()

    @property
    def is_on(self) -> bool | None:
        """Return true if the siren is on."""

        return self._on

    def __on_change(self, value: int) -> None:
        self._on = value != 0
        self.schedule_update_ha_state()

    async def __async_turn_on(self, volume_level: int, duration: int) -> None:
        await self._io_output.async_on(volume_level)

        if duration >= 0:
            if await self._sequencer.async_sleep(duration):
                # we switch it off if the sleep wasn't cancelled
                await self._io_output.async_off()

    async def __async_turn_off(self) -> None:
        await self._io_output.async_off()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the siren to turn on."""

        volume_level = int(kwargs.get(ATTR_VOLUME_LEVEL, 1) * 255)
        duration = kwargs.get(ATTR_DURATION, -1)

        await self._sequencer.async_run(self.__async_turn_on(volume_level, duration))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the siren to turn off."""

        await self._sequencer.async_run(self.__async_turn_off())

    async def async_will_remove_from_hass(self) -> None:
        """Remove siren from hass and release it."""

        await self.async_turn_off()
        await self._io_output.async_release()
