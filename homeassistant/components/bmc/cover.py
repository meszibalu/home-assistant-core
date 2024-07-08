"""Platform for sensor integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.bmc.devices import Devices
from homeassistant.components.bmc.hub import BmcHub
from homeassistant.components.bmc.two_way_output import TwoWayOutput, TwoWayOutputType
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the cover platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcCover(hub, **config.options)])

class BmcCover(CoverEntity):
    """Representation of a cover."""

    def __init__(self, hub: BmcHub, device_class: str, output_type: str,
                 address: int, output: int, invert: bool, timeout: float,
                 address2: int, output2: int, invert2: bool, timeout2: float,
                 **ignored: any) -> None:
        self._attr_unique_id = Devices.get_unique_id(address, output)
        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = CoverDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning(f"Unknown device class '{device_class}.")

        output_type_enum = TwoWayOutputType(output_type)

        match output_type_enum:
            case TwoWayOutputType.NORMALLY_OPEN | TwoWayOutputType.NORMALLY_CLOSED:
                supported_features = CoverEntityFeature(0)
            case TwoWayOutputType.PWM:
                supported_features = CoverEntityFeature.SET_POSITION
            case TwoWayOutputType.TWO_DIRECTION:
                supported_features = CoverEntityFeature.SET_POSITION | CoverEntityFeature.STOP
            case _:
                raise ValueError(f"Unknown output type '{output_type_enum}'.")

        self._attr_supported_features = (
                CoverEntityFeature.OPEN |
                CoverEntityFeature.CLOSE |
                supported_features
        )

        self._lock = asyncio.Lock()
        self._two_way = TwoWayOutput.open(hub, output_type_enum, address, output, invert, timeout,
                                          address2, output2, invert2, timeout2)

        self._set_current_cover_position()
        self._attr_is_opening = False
        self._attr_is_closing = False

    @property
    def current_cover_position(self) -> int:
        return self._attr_current_cover_position

    def _set_current_cover_position(self) -> None:
        self._attr_current_cover_position = int(self._two_way.position)

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        return self._attr_is_opening

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        return self._attr_is_closing

    @property
    def is_closed(self) -> bool:
        return self._two_way.position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        _LOGGER.info(f"Opening cover '{self.unique_id}'.")

        self._two_way.cancel()

        async with self._lock:
            self._attr_is_opening = True
            self.schedule_update_ha_state()

            if await self._two_way.async_move(100):
                # if the movement wasn't cancelled, we update the current position
                self._set_current_cover_position()

                _LOGGER.info(f"Cover '{self.unique_id}' was moved to position '{self.current_cover_position}'.")

            self._attr_is_opening = False
            self.schedule_update_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        _LOGGER.info(f"Closing cover '{self.unique_id}'.")

        self._two_way.cancel()

        async with self._lock:
            self._attr_is_closing = True
            self.schedule_update_ha_state()

            if await self._two_way.async_move(0):
                # if the movement wasn't cancelled, we update the current position
                self._set_current_cover_position()

                _LOGGER.info(f"Cover '{self.unique_id}' was moved to position '{self.current_cover_position}'.")

            self._attr_is_closing = False
            self.schedule_update_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = kwargs[ATTR_POSITION]

        _LOGGER.info(f"Moving cover '{self.unique_id}' to position '{position}'.")

        self._two_way.cancel()

        async with self._lock:
            if position > self._two_way.position:
                self._attr_is_opening = True
                self._attr_is_closing = False
            elif position < self._two_way.position:
                self._attr_is_opening = False
                self._attr_is_closing = True

            self.schedule_update_ha_state()

            if await self._two_way.async_move(position):
                # if the movement wasn't cancelled, we update the current position
                self._set_current_cover_position()

                _LOGGER.info(f"Cover '{self.unique_id}' was moved to position '{self.current_cover_position}'.")

            self._attr_is_opening = False
            self._attr_is_closing = False
            self.schedule_update_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        _LOGGER.info(f"Stopping cover '{self.unique_id}'.")

        self._two_way.cancel()

        # the lock waits till the previous operation completes and updates the state
        async with self._lock:
            self._set_current_cover_position()
            self.schedule_update_ha_state()

        _LOGGER.info(f"Cover '{self.unique_id}' was moved to position '{self.current_cover_position}'.")

    async def async_will_remove_from_hass(self) -> None:
        await self.async_stop_cover()

        async with self._lock:
            self._two_way.release()
