"""Platform for switch integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bmc.hub import BmcHub
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry
from .devices import Devices


async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the Bali Muvek Switch platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcSwitch(hub, **config.options)])

class BmcSwitch(SwitchEntity):
    """Representation of a Bali Muvek Switch."""

    def __init__(self, hub: BmcHub, address: int, output: int, invert: bool, **ignored: any) -> None:
        """Initialize a BmcSwitch."""

        self._attr_unique_id = Devices.get_unique_id(address, output)
        self._attr_should_poll = False

        self._io_output = hub.use_io_output(address, output, False, invert)

        self._switch_off()

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""

        return self._on

    def _switch_on(self) -> None:
        self._io_output.on()
        self._on = True

    def _switch_off(self) -> None:
        self._io_output.off()
        self._on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""

        self._switch_on()
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""

        self._switch_off()
        self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await self.async_turn_off()

        self._io_output.release()
