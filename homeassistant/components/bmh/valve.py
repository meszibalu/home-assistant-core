"""Platform for valve integration.

A valve is connected to one or two I/O Outputs and drives them to move the
valve between opened and closed state. Some valve types support positioning.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BmhConfigEntry
from .hub import BmhHub
from .strings import Strings
from .two_way_output import TwoWayOutput, TwoWayOutputType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: BmhConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create valve entity."""

    entity = await __async_create(hass, **config.options)
    add_entities([entity])


async def __async_create(
    hass: HomeAssistant,
    device_class: str,
    output_type: str,
    address: int,
    output: int,
    invert: bool,
    timeout: float,
    address2: int,
    output2: int,
    invert2: bool,
    timeout2: float,
    **ignored: Any,
) -> BmhValve:
    hub = await BmhHub.async_get(hass)

    return BmhValve(
        hub,
        device_class,
        output_type,
        address,
        output,
        invert,
        timeout,
        address2,
        output2,
        invert2,
        timeout2,
    )


class BmhValve(ValveEntity):
    """Representation of a valve."""

    def __init__(
        self,
        hub: BmhHub,
        device_class: str,
        output_type_str: str,
        address: int,
        output: int,
        invert: bool,
        timeout: float,
        address2: int,
        output2: int,
        invert2: bool,
        timeout2: float,
    ) -> None:
        """Initialize a new valve."""

        self._attr_unique_id = Strings.get_unique_id(address, output)
        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = ValveDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning("Unknown device class '%s'", device_class)

        output_type = TwoWayOutputType(output_type_str)

        match output_type:
            case TwoWayOutputType.NORMALLY_CLOSED | TwoWayOutputType.NORMALLY_OPENED:
                reports_position = False
                supported_features = ValveEntityFeature(0)
            case TwoWayOutputType.PWM:
                reports_position = True
                supported_features = ValveEntityFeature.SET_POSITION
            case TwoWayOutputType.TWO_DIRECTION:
                reports_position = True
                supported_features = (
                    ValveEntityFeature.SET_POSITION | ValveEntityFeature.STOP
                )
            case _:
                raise ValueError(f"Unknown output type '{output_type}'.")

        self._attr_reports_position = reports_position
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE | supported_features
        )

        self._two_way = TwoWayOutput.create(
            hub,
            output_type,
            address,
            output,
            invert,
            timeout,
            address2,
            output2,
            invert2,
            timeout2,
            self.__on_change,
        )

    async def async_added_to_hass(self) -> None:
        """Open the valve."""

        await self._two_way.async_open()

    async def async_will_remove_from_hass(self) -> None:
        """Remove valve from hass and release it."""

        await self._two_way.async_release()

    def __on_change(self) -> None:
        if self.is_opening:
            _LOGGER.info("Opening valve '%s'", self.unique_id)
        elif self.is_closing:
            _LOGGER.info("Closing valve '%s'", self.unique_id)
        elif self.current_valve_position is not None:
            _LOGGER.info(
                "Valve '%s' is at unknown position.",
                self.unique_id,
            )
        else:
            _LOGGER.info(
                "Valve '%s' was moved to position '%d'",
                self.unique_id,
                self.current_valve_position,
            )

        self.schedule_update_ha_state()

    @property
    def current_valve_position(self) -> int | None:
        """Return the current position of the valve."""

        if self._two_way.position is None:
            return None
        return round(self._two_way.position * 100)

    @property
    def is_opening(self) -> bool | None:
        """Return true if the valve is opening."""
        return self._two_way.opening

    @property
    def is_closing(self) -> bool | None:
        """Return true if the valve is closing."""
        return self._two_way.closing

    @property
    def is_closed(self) -> bool | None:
        """Return true if the valve is closed."""

        if self._two_way.position is None:
            return None

        return self._two_way.position == 0

    async def async_open_valve(self) -> None:
        """Instruct the valve to open."""

        await self._two_way.async_move(1)

    async def async_close_valve(self) -> None:
        """Instruct the valve to close."""

        await self._two_way.async_move(0)

    async def async_set_valve_position(self, position: int) -> None:
        """Instruct the valve to move to the given position."""

        await self._two_way.async_move(position / 100)

    async def async_stop_valve(self) -> None:
        """Instruct the valve to stop at current position."""

        _LOGGER.info("Stopping valve '%s'", self.unique_id)

        await self._two_way.async_stop()
