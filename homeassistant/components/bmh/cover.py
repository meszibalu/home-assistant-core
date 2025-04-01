"""Platform for cover integration.

A cover is connected to one or two I/O Outputs and drives them to move the
cover between opened and closed state. Some cover types support positioning.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
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
    """Create cover entity."""

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
) -> BmhCover:
    hub = await BmhHub.async_get(hass)

    entity = BmhCover(device_class)
    await entity.async_init(
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
    )

    return entity


class BmhCover(CoverEntity):
    """Representation of a cover."""

    def __init__(self, device_class: str) -> None:
        """Initialize a new cover.

        async_init() is required to finish I/O initialization.
        """
        self._attr_should_poll = False

        if device_class is not None:
            try:
                self._attr_device_class = CoverDeviceClass(device_class)
            except ValueError:
                _LOGGER.warning("Unknown device class '%s'", device_class)

    async def async_init(
        self,
        hub: BmhHub,
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
        """Finish initialization and open I/O."""

        self._attr_unique_id = Strings.get_unique_id(address, output)

        output_type = TwoWayOutputType(output_type_str)

        match output_type:
            case TwoWayOutputType.NORMALLY_CLOSED | TwoWayOutputType.NORMALLY_OPENED:
                supported_features = CoverEntityFeature(0)
            case TwoWayOutputType.PWM:
                supported_features = CoverEntityFeature.SET_POSITION
            case TwoWayOutputType.TWO_DIRECTION:
                supported_features = (
                    CoverEntityFeature.SET_POSITION | CoverEntityFeature.STOP
                )
            case _:
                raise ValueError(f"Unknown output type '{output_type}'.")

        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | supported_features
        )

        # pylint: disable=attribute-defined-outside-init
        self._two_way = await TwoWayOutput.async_open(
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

    @property
    def current_cover_position(self) -> int:
        """Return the current position of the cover."""

        return round(self._two_way.position)

    @property
    def is_opening(self) -> bool | None:
        """Return true if the cover is opening."""

        return self._two_way.opening

    @property
    def is_closing(self) -> bool | None:
        """Return true if the cover is closing."""

        return self._two_way.closing

    @property
    def is_closed(self) -> bool:
        """Return true if the cover is closed."""

        return self._two_way.position == 0

    def __on_change(self) -> None:
        if self.is_opening:
            _LOGGER.info("Opening cover '%s'", self.unique_id)
        elif self.is_closing:
            _LOGGER.info("Closing cover '%s'", self.unique_id)
        else:
            _LOGGER.info(
                "Cover '%s' was moved to position '%d'",
                self.unique_id,
                self.current_cover_position,
            )

        self.schedule_update_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to open."""

        await self._two_way.async_move(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to close."""

        await self._two_way.async_move(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Instruct the cover to move to the given position."""

        position = kwargs[ATTR_POSITION]
        await self._two_way.async_move(position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to stop at current position."""

        _LOGGER.info("Stopping cover '%s'", self.unique_id)

        await self._two_way.async_stop()

    async def async_will_remove_from_hass(self) -> None:
        """Remove cover from hass and release it."""

        await self._two_way.async_release()
