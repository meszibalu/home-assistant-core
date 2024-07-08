"""Platform for sensor integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.bmc.devices import Devices
from homeassistant.components.bmc.hub import BmcHub
from homeassistant.components.bmc.two_way_output import TwoWayOutput, TwoWayOutputType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BmcConfigEntry
from ..valve import ValveEntity, ValveDeviceClass, ValveEntityFeature

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, config: BmcConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up the valve platform."""

    hub = BmcHub.get(hass)

    add_entities([BmcValve(hub, **config.options)])

class BmcValve(ValveEntity):
    """Representation of a valve."""

    def __init__(self, hub: BmcHub, device_class: str, output_type: str,
                 address: int, output: int, invert: bool, timeout: float,
                 address2: int, output2: int, invert2: bool, timeout2: float,
                 **ignored: any) -> None:
        self._attr_unique_id = Devices.get_unique_id(address, output)
        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = ValveDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning(f"Unknown device class '{device_class}.")

        output_type_enum = TwoWayOutputType(output_type)

        match output_type_enum:
            case TwoWayOutputType.NORMALLY_OPEN | TwoWayOutputType.NORMALLY_CLOSED:
                reports_position = False
                supported_features = ValveEntityFeature(0)
            case TwoWayOutputType.PWM:
                reports_position = True
                supported_features = ValveEntityFeature.SET_POSITION
            case TwoWayOutputType.TWO_DIRECTION:
                reports_position = True
                supported_features = ValveEntityFeature.SET_POSITION | ValveEntityFeature.STOP
            case _:
                raise ValueError(f"Unknown output type '{output_type_enum}'.")

        self._attr_reports_position = reports_position
        self._attr_supported_features = (
                ValveEntityFeature.OPEN |
                ValveEntityFeature.CLOSE |
                supported_features
        )

        self._lock = asyncio.Lock()
        self._two_way = TwoWayOutput.open(hub, output_type_enum, address, output, invert, timeout,
                                          address2, output2, invert2, timeout2)

        self._set_current_valve_position()
        self._attr_is_opening = False
        self._attr_is_closing = False

    @property
    def current_valve_position(self) -> int:
        return self._attr_current_valve_position

    def _set_current_valve_position(self) -> None:
        self._attr_current_valve_position = int(self._two_way.position)

    @property
    def is_opening(self) -> bool | None:
        """Return if the valve is opening or not."""
        return self._attr_is_opening

    @property
    def is_closing(self) -> bool | None:
        """Return if the valve is closing or not."""
        return self._attr_is_closing

    @property
    def is_closed(self) -> bool:
        return self._two_way.position == 0

    async def async_open_valve(self) -> None:
        _LOGGER.info(f"Opening valve '{self.unique_id}'.")

        self._two_way.cancel()

        async with self._lock:
            self._attr_is_opening = True
            self.schedule_update_ha_state()

            if await self._two_way.async_move(100):
                # if the movement wasn't cancelled, we update the current position
                self._set_current_valve_position()

                _LOGGER.info(f"Valve '{self.unique_id}' was moved to position '{self.current_valve_position}'.")

            self._attr_is_opening = False
            self.schedule_update_ha_state()

    async def async_close_valve(self) -> None:
        _LOGGER.info(f"Closing valve '{self.unique_id}'.")

        self._two_way.cancel()

        async with self._lock:
            self._attr_is_closing = True
            self.schedule_update_ha_state()

            if await self._two_way.async_move(0):
                # if the movement wasn't cancelled, we update the current position
                self._set_current_valve_position()

                _LOGGER.info(f"Valve '{self.unique_id}' was moved to position '{self.current_valve_position}'.")

            self._attr_is_closing = False
            self.schedule_update_ha_state()

    async def async_set_valve_position(self, position: int) -> None:
        _LOGGER.info(f"Moving valve '{self.unique_id}' to position '{position}'.")

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
                self._set_current_valve_position()

                _LOGGER.info(f"Valve '{self.unique_id}' was moved to position '{self.current_valve_position}'.")

            self._attr_is_opening = False
            self._attr_is_closing = False
            self.schedule_update_ha_state()

    async def async_stop_valve(self) -> None:
        _LOGGER.info(f"Stopping valve '{self.unique_id}'.")

        self._two_way.cancel()

        # the lock waits till the previous operation completes and updates the state
        async with self._lock:
            self._set_current_valve_position()
            self.schedule_update_ha_state()

        _LOGGER.info(f"Valve '{self.unique_id}' was moved to position '{self.current_valve_position}'.")

    async def async_will_remove_from_hass(self) -> None:
        await self.async_stop_valve()

        async with self._lock:
            self._two_way.release()
