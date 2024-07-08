"""Platform for switch integration."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.bmc.hub import BmcHub
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry
from .devices import Devices
from .sleeper import Sleeper
from ..siren import SirenEntity, SirenEntityFeature, ATTR_DURATION, ATTR_VOLUME_LEVEL


async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the Bali Muvek Switch platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcSiren(hub, **config.options)])

class BmcSiren(SirenEntity):
    """Representation of a Bali Muvek Siren."""

    def __init__(self, hub: BmcHub, address: int, output: int, pwm: bool, invert: bool, **ignored: any) -> None:
        """Initialize a BmcSiren."""

        self._attr_unique_id = Devices.get_unique_id(address, output)
        self._attr_should_poll = False

        volume_feature = SirenEntityFeature.VOLUME_SET if pwm else SirenEntityFeature(0)

        self._attr_supported_features = (
                SirenEntityFeature.TURN_ON |
                SirenEntityFeature.TURN_OFF |
                SirenEntityFeature.DURATION |
                volume_feature
        )

        self._io_output = hub.use_io_output(address, output, pwm, invert)

        self._switch_off()

        self._lock = asyncio.Lock()
        self._sleeper = Sleeper()

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""

        return self._on

    def _switch_on(self, volume_level: int) -> None:
        self._io_output.on(volume_level)
        self._on = True

    def _switch_off(self) -> None:
        self._io_output.off()
        self._on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._sleeper.cancel()

        volume_level = int(kwargs.get(ATTR_VOLUME_LEVEL, 1) * 255)

        async with self._lock:
            if ATTR_DURATION in kwargs:
                duration = kwargs.get(ATTR_DURATION)

                self._switch_on(volume_level)
                self.schedule_update_ha_state()

                if await self._sleeper.sleep(duration):
                    # we switch it off if the sleep wasn't cancelled
                    self._switch_off()
                    self.schedule_update_ha_state()
            else:
                self._switch_on(volume_level)
                self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._sleeper.cancel()

        async with self._lock:
            self._switch_off()
            self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await self.async_turn_off()

        self._io_output.release()
