"""Platform for event integration.

An event is connected to an I/O Input and it acts as a push button.
It emits a begin event if the input rises. It emits an end event if the input
falls. The end event also contains the duration that it spent in high state.
"""

from __future__ import annotations

import logging
import threading
import time

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BmhConfigEntry
from .hub import BmhHub
from .strings import Strings

_LOGGER = logging.getLogger(__name__)

BEGIN_EVENT_TYPE: str = "begin"
END_EVENT_TYPE: str = "end"

ATTR_DURATION: str = "duration"


async def async_setup_entry(
    hass: HomeAssistant,
    config: BmhConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create event entity."""

    entity = await __async_create(hass, **config.options)
    add_entities([entity])


async def __async_create(
    hass: HomeAssistant,
    device_class: str,
    address: int,
    input: int,
    invert: bool,
    **ignored,
) -> BmhEvent:
    hub = await BmhHub.async_get(hass)

    return BmhEvent(hub, device_class, address, input, invert)


class BmhEvent(EventEntity):
    """Representation of an event."""

    def __init__(
        self, hub: BmhHub, device_class: str, address: int, input: int, invert: bool
    ) -> None:
        """Initialize a new event."""

        self._attr_unique_id = Strings.get_unique_id(address, input)
        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = EventDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning("Unknown device class '%s'", device_class)

        self._attr_event_types = [BEGIN_EVENT_TYPE, END_EVENT_TYPE]

        self._lock = threading.Lock()
        self._last_rise_ns: int | None = None

        self._io_input = hub.create_io_input(
            address, input, invert, self.__on_change, None
        )

    async def async_added_to_hass(self) -> None:
        """Open the event."""

        await self._io_input.async_open()

        self._io_input.read()

    async def async_will_remove_from_hass(self) -> None:
        """Remove event from hass and release it."""

        await self._io_input.async_release()

    def _begin(self) -> None:
        _LOGGER.debug("Begin event on '%s'", self._io_input.device_port)

        self._last_rise_ns = time.monotonic_ns()

        self._trigger_event(BEGIN_EVENT_TYPE)
        self.schedule_update_ha_state()

    def _end(self) -> None:
        duration = (time.monotonic_ns() - self._last_rise_ns) // 1_000_000  # type: ignore[operator]

        _LOGGER.debug(
            "End event on '%s'. Duration: %d msec",
            self._io_input.device_port,
            duration,
        )

        self._last_rise_ns = None

        self._trigger_event(END_EVENT_TYPE, {ATTR_DURATION: duration})
        self.schedule_update_ha_state()

    def __on_change(self, value: bool) -> None:
        # The callback is called normally in a sequence of
        # ..., True, False, True, False, ...
        # If callback is called with the same value as before, it means
        # there was a value, ~value, value sequence, so we missed the
        # ~value callback.

        with self._lock:
            if value:
                if self._last_rise_ns is not None:
                    self._end()

                self._begin()
            else:
                if self._last_rise_ns is None:
                    self._begin()

                self._end()
