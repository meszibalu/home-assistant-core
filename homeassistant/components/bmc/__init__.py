"""The Bali Muvek Controller integration."""

from __future__ import annotations

import logging
from enum import StrEnum

from homeassistant.components.bmc.const import DOMAIN
from homeassistant.components.bmc.hub import BmcHub
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_PLATFORM
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE
]

type BmcConfigEntry = ConfigEntry[BmcHass]  # noqa: F821

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config: BmcConfigEntry) -> bool:
    """Set up Bali Muvek Controller from a config entry."""

    platform = config.options[CONF_PLATFORM]

    if platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(config, [platform])
        return True
    else:
        _LOGGER.warning(f"Platform '{platform}' is not supported.")
        return False

async def async_unload_entry(hass: HomeAssistant, config: BmcConfigEntry) -> bool:
    """Unload a config entry."""

    platform = config.options[CONF_PLATFORM]

    if platform in PLATFORMS:
        return await hass.config_entries.async_unload_platforms(config, [platform])
    else:
        return True
