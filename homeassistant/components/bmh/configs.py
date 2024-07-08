"""Configuration parser utility."""

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.event import EventDeviceClass
from homeassistant.core import HomeAssistant

from .const import (
    CONF_1W_PORT,
    CONF_ADDRESS,
    CONF_ADDRESS2,
    CONF_DEVICE_CLASS,
    CONF_INVERT,
    CONF_INVERT2,
    CONF_IO_INPUT,
    CONF_IO_OUTPUT,
    CONF_IO_OUTPUT2,
    CONF_PWM,
    CONF_TIMEOUT,
    CONF_TIMEOUT2,
)
from .hub import BmhHub
from .strings import Strings
from .two_way_output import TwoWayOutputType


class Configs:
    """Configuration parser utility class."""

    @staticmethod
    def parse_address(options: dict[str, Any], key: str = CONF_ADDRESS) -> int:
        """Parse address string from the options."""

        if key not in options:
            raise ValueError("Missing address.")

        address = str(options[key])

        if len(address) != 3:
            raise ValueError(
                f"Invalid address '0x{address}'. "
                "It must be 0xBAA where B is the bus and "
                f"AA is the device address (10 - 6F)."
            )

        try:
            return int(address, 16)
        except ValueError as e:
            raise ValueError(
                f"Invalid address '0x{address}'. "
                "It must be 0xBAA where B is the bus and "
                "AA is the device address (10 - 6F)."
            ) from e

    @staticmethod
    def __get_used_error(resource: str) -> ValueError:
        return ValueError(f"Resource '{resource}' is already used by another entity.")

    @staticmethod
    def __get_io_input_used_error(address: int, input: int) -> ValueError:
        return Configs.__get_used_error(Strings.get_io_input(address, input))

    @staticmethod
    def __get_io_output_used_error(address: int, output: int) -> ValueError:
        return Configs.__get_used_error(Strings.get_io_output(address, output))

    @staticmethod
    def __get_1w_port_used_error(address: int, port: int) -> ValueError:
        return Configs.__get_used_error(Strings.get_1w_port(address, port))

    @staticmethod
    async def __async_parse_io_input(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        address = Configs.parse_address(options)
        io_input = int(options[CONF_IO_INPUT])

        hub = await BmhHub.async_get(hass)

        if not hub.is_io_input_available(address, io_input):
            raise Configs.__get_io_input_used_error(address, io_input)

        await hub.async_check_device_present(address)

        return {
            CONF_ADDRESS: address,
            CONF_IO_INPUT: io_input,
            CONF_INVERT: options.get(CONF_INVERT, False),
        }

    @staticmethod
    async def __async_parse_io_output(
        hass: HomeAssistant, options: dict[str, Any], pwm: bool, suffix: str = ""
    ) -> dict[str, Any]:
        address = Configs.parse_address(options, CONF_ADDRESS + suffix)
        io_output = int(options[CONF_IO_OUTPUT + suffix])

        hub = await BmhHub.async_get(hass)

        if not hub.is_io_output_available(address, io_output):
            raise Configs.__get_io_output_used_error(address, io_output)

        await hub.async_check_device_present(address)

        if pwm:
            pwm_options = {CONF_PWM + suffix: options.get(CONF_PWM + suffix, False)}
        else:
            pwm_options = {}

        return {
            CONF_ADDRESS + suffix: address,
            CONF_IO_OUTPUT + suffix: io_output,
            **pwm_options,
            CONF_INVERT + suffix: options.get(CONF_INVERT + suffix, False),
        }

    @staticmethod
    async def __async_parse_io_output_two_way(
        hass: HomeAssistant, output_type: TwoWayOutputType, options: dict[str, Any]
    ) -> dict[str, Any]:
        parsed = await Configs.__async_parse_io_output(hass, options, False, "")

        match output_type:
            case (
                TwoWayOutputType.NORMALLY_CLOSED
                | TwoWayOutputType.NORMALLY_OPENED
                | TwoWayOutputType.PWM
            ):
                parsed.update(
                    {
                        CONF_ADDRESS2: 0,
                        CONF_IO_OUTPUT2: 0,
                        CONF_INVERT2: 0,
                    }
                )
            case TwoWayOutputType.TWO_DIRECTION:
                parsed2 = await Configs.__async_parse_io_output(
                    hass, options, False, "2"
                )

                if (
                    parsed[CONF_ADDRESS] == parsed2[CONF_ADDRESS2]
                    and parsed[CONF_IO_OUTPUT] == parsed2[CONF_IO_OUTPUT2]
                ):
                    raise ValueError("Open and close output is the same.")

                parsed.update(parsed2)

        parsed.update(
            {
                CONF_TIMEOUT: float(options.get(CONF_TIMEOUT, 0)),
                CONF_TIMEOUT2: float(options.get(CONF_TIMEOUT2, 0)),
            }
        )

        return parsed

    @staticmethod
    async def __async_parse_1w_port(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        address = Configs.parse_address(options)
        port = int(options[CONF_1W_PORT])

        hub = await BmhHub.async_get(hass)

        if not hub.is_1w_port_available(address, port):
            raise Configs.__get_1w_port_used_error(address, port)

        await hub.async_check_device_present(address)

        return {CONF_ADDRESS: address, CONF_1W_PORT: port}

    @staticmethod
    def __parse_list(
        options: dict[str, Any], key: str, values: list[str]
    ) -> dict[str, Any]:
        value = options.get(key)

        if value is not None and value not in values:
            raise ValueError(f"Unknown value '{value}'.")

        return {key: value}

    @staticmethod
    async def async_parse_binary_sensor(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse binary sensor entity options."""

        parsed = await Configs.__async_parse_io_input(hass, options)

        parsed.update(
            Configs.__parse_list(
                options, CONF_DEVICE_CLASS, list(BinarySensorDeviceClass)
            )
        )

        return parsed

    @staticmethod
    async def async_parse_cover(
        hass: HomeAssistant, output_type: TwoWayOutputType, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse cover entity options."""

        return await Configs.__async_parse_io_output_two_way(hass, output_type, options)

    @staticmethod
    async def async_parse_event(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse event entity options."""

        parsed = await Configs.__async_parse_io_input(hass, options)

        parsed.update(
            Configs.__parse_list(options, CONF_DEVICE_CLASS, list(EventDeviceClass))
        )

        return parsed

    @staticmethod
    async def async_parse_light(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse light entity options."""

        return await Configs.__async_parse_io_output(hass, options, True)

    @staticmethod
    async def async_parse_sensor(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse sensor entity options."""

        return await Configs.__async_parse_1w_port(hass, options)

    @staticmethod
    async def async_parse_siren(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse siren entity options."""

        return await Configs.__async_parse_io_output(hass, options, True)

    @staticmethod
    async def async_parse_switch(
        hass: HomeAssistant, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse switch entity options."""

        return await Configs.__async_parse_io_output(hass, options, False)

    @staticmethod
    async def async_parse_valve(
        hass: HomeAssistant, output_type: TwoWayOutputType, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse valve entity options."""

        return await Configs.__async_parse_io_output_two_way(hass, output_type, options)
