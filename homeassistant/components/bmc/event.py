"""Platform for sensor integration."""

from __future__ import annotations

import logging
import time

from homeassistant.components.bmc.devices import Devices
from homeassistant.components.bmc.hub import BmcHub
from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry

_LOGGER = logging.getLogger(__name__)

BEGIN_EVENT_TYPE: str = "begin"
END_EVENT_TYPE: str = "end"

ATTR_DURATION: str = "duration"

async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcEvent(hub, **config.options)])

class BmcEvent(EventEntity):
    """Representation of a button."""

    def __init__(self, hub: BmcHub, address: int, input: int, device_class: str, invert: bool,
                 **ignored) -> None:
        self._attr_unique_id = Devices.get_unique_id(address, input)
        self._attr_should_poll = False
        self._attr_event_types = [BEGIN_EVENT_TYPE, END_EVENT_TYPE]

        if device_class is not None:
            try:
                self._attr_device_class = EventDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning(f"Unknown device class '{device_class}.")

        self._last_rise_ns = None
        self._io_input = hub.use_io_input(address, input, invert, self.__callback)

    def __callback(self) -> None:
        value = self._io_input.read()

        if value and self._last_rise_ns is None:
            self._last_rise_ns = time.monotonic_ns()

            self._trigger_event(BEGIN_EVENT_TYPE)
            self.schedule_update_ha_state()
        elif not value and self._last_rise_ns is not None:
            duration = (time.monotonic_ns() - self._last_rise_ns) // 1_000_000
            self._last_rise_ns = None

            self._trigger_event(END_EVENT_TYPE, {ATTR_DURATION: duration})
            self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self._io_input.release()