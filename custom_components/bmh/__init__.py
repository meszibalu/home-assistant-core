"""The Bali Művek Home Controller integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant

from .hub import BmhHub

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
]

type BmhConfigEntry = ConfigEntry[BmhHub]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: BmhConfigEntry) -> bool:
    """Set up Bali Művek Home Controller from a config entry."""

    platform = config.options[CONF_PLATFORM]

    if platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(config, [platform])
        return True

    _LOGGER.warning("Platform '%s' is not supported", platform)
    return False


async def async_unload_entry(hass: HomeAssistant, config: BmhConfigEntry) -> bool:
    """Unload a config entry."""

    platform = config.options[CONF_PLATFORM]

    if platform in PLATFORMS:
        return await hass.config_entries.async_unload_platforms(config, [platform])

    return True
