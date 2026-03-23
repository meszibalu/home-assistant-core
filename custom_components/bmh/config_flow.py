"""Config flow for Bali Művek Home Controller integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.event import EventDeviceClass
from homeassistant.components.valve import ValveDeviceClass
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    Selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from . import PLATFORMS
from .configs import Configs
from .const import (
    CONF_1W_PORT,
    CONF_ADDRESS,
    CONF_ADDRESS2,
    CONF_DEVICE_CLASS,
    CONF_INVERT,
    CONF_IO_INPUT,
    CONF_IO_OUTPUT,
    CONF_IO_OUTPUT2,
    CONF_PWM,
    CONF_TIMEOUT,
    CONF_TWO_WAY_OUTPUT_TYPE,
    DOMAIN,
)
from .strings import Strings
from .two_way_output import TwoWayOutputType

SELECTOR_ADDRESS = TextSelector(TextSelectorConfig(prefix="0x"))
SELECTOR_IO_INPUT = NumberSelector(
    NumberSelectorConfig(min=0, max=5, mode=NumberSelectorMode.BOX)
)
SELECTOR_IO_OUTPUT = NumberSelector(
    NumberSelectorConfig(min=0, max=5, mode=NumberSelectorMode.BOX)
)
SELECTOR_1W_PORT = NumberSelector(
    NumberSelectorConfig(min=0, max=9, mode=NumberSelectorMode.BOX)
)
SELECTOR_TIMEOUT = NumberSelector(
    NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX, unit_of_measurement="sec")
)


def create_list_selector(
    values: list[Any],
    mode: SelectSelectorMode = SelectSelectorMode.DROPDOWN,
    sort: bool = True,
) -> SelectSelector:
    """Create a SelectSelector."""

    return SelectSelector(SelectSelectorConfig(options=values, mode=mode, sort=sort))


def create_io_input_schema(extras: dict[vol.Marker, Selector[Any]]) -> vol.Schema:
    """Create schema for an I/O input."""

    return vol.Schema(
        {
            vol.Required(CONF_ADDRESS): SELECTOR_ADDRESS,
            vol.Required(CONF_IO_INPUT): SELECTOR_IO_INPUT,
            vol.Optional(CONF_INVERT, default=False): BooleanSelector(),
            **extras,
        }
    )


def create_io_output_schema(
    extras: dict[vol.Marker, Selector[Any]] | None = None,
    pwm: bool = False,
    suffix: str = "",
) -> vol.Schema:
    """Create schema for an I/O output."""

    if extras is None:
        extras = {}

    if pwm:
        pwm_schema: dict[vol.Marker, Selector[Any]] = {
            vol.Optional(CONF_PWM + suffix, default=False): BooleanSelector()
        }
    else:
        pwm_schema = {}

    return vol.Schema(
        {
            vol.Required(CONF_ADDRESS + suffix): SELECTOR_ADDRESS,
            vol.Required(CONF_IO_OUTPUT + suffix): SELECTOR_IO_OUTPUT,
            **pwm_schema,
            vol.Optional(CONF_INVERT + suffix, default=False): BooleanSelector(),
            **extras,
        }
    )


def create_io_output_two_way_select_schema(device_classes: list[str]) -> vol.Schema:
    """Create schema for a two-way I/O output."""

    return vol.Schema(
        {
            vol.Optional(CONF_DEVICE_CLASS): create_list_selector(device_classes),
            vol.Required(CONF_TWO_WAY_OUTPUT_TYPE): create_list_selector(
                list(TwoWayOutputType), sort=False
            ),
        }
    )


def create_io_output_two_way_output1_schema() -> vol.Schema:
    """Create schema for two-way I/O output1."""

    return create_io_output_schema(
        {
            vol.Required(CONF_TIMEOUT): SELECTOR_TIMEOUT,
            vol.Required(CONF_TIMEOUT + "2"): SELECTOR_TIMEOUT,
        }
    )


def create_io_output_two_way_output2_schema() -> vol.Schema:
    """Create schema for two-way I/O output2."""

    output = create_io_output_schema({vol.Required(CONF_TIMEOUT): SELECTOR_TIMEOUT})
    output2 = create_io_output_schema(
        {vol.Required(CONF_TIMEOUT + "2"): SELECTOR_TIMEOUT}, suffix="2"
    )

    return output.extend(output2.schema)


async def get_next_step(user_input: dict[str, Any]) -> str:
    """Get the next step after platform selection. It return the platform specific configuration step."""

    return user_input[CONF_PLATFORM]


def create_two_way_next_step(
    platform: str,
) -> Callable[[dict[str, Any]], Coroutine[Any, Any, str]]:
    """Get the next step after two-way mode selection."""

    async def get_two_way_next_step(user_input: dict[str, Any]) -> str:
        output_type = TwoWayOutputType(user_input[CONF_TWO_WAY_OUTPUT_TYPE])

        match output_type:
            case (
                TwoWayOutputType.NORMALLY_CLOSED
                | TwoWayOutputType.NORMALLY_OPENED
                | TwoWayOutputType.PWM
            ):
                return f"{platform}_output1"
            case TwoWayOutputType.TWO_DIRECTION:
                return f"{platform}_output2"
            case _:
                raise ValueError(f"Unknown output type '{output_type}'.")

    return get_two_way_next_step


async def async_validate_binary_sensor(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate binary sensor entity options."""

    try:
        return await Configs.async_parse_binary_sensor(
            handler.parent_handler.hass, user_input
        )
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


async def async_validate_cover(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate cover entity options."""

    try:
        return await Configs.async_parse_cover(
            handler.parent_handler.hass,
            handler.options[CONF_TWO_WAY_OUTPUT_TYPE],
            user_input,
        )
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


async def async_validate_event(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate event entity options."""

    try:
        return await Configs.async_parse_event(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


async def async_validate_light(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate light entity options."""

    try:
        return await Configs.async_parse_light(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


async def async_validate_sensor(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor entity options."""

    try:
        return await Configs.async_parse_sensor(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


async def async_validate_siren(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate siren entity options."""

    try:
        return await Configs.async_parse_siren(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


async def async_validate_switch(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate switch entity options."""

    try:
        return await Configs.async_parse_switch(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


async def async_validate_valve(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate valve entity options."""

    try:
        return await Configs.async_parse_valve(
            handler.parent_handler.hass,
            handler.options[CONF_TWO_WAY_OUTPUT_TYPE],
            user_input,
        )
    except ValueError as e:
        raise SchemaFlowError(str(e)) from e


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=vol.Schema(
            {
                vol.Required(CONF_PLATFORM): create_list_selector(
                    PLATFORMS, mode=SelectSelectorMode.LIST
                )
            }
        ),
        next_step=get_next_step,
    ),
    "binary_sensor": SchemaFlowFormStep(
        schema=create_io_input_schema(
            {
                vol.Optional(CONF_DEVICE_CLASS): create_list_selector(
                    list(BinarySensorDeviceClass)
                )
            }
        ),
        validate_user_input=async_validate_binary_sensor,
    ),
    "cover": SchemaFlowFormStep(
        schema=create_io_output_two_way_select_schema(list(CoverDeviceClass)),
        next_step=create_two_way_next_step("cover"),
    ),
    "cover_output1": SchemaFlowFormStep(
        schema=create_io_output_two_way_output1_schema(),
        validate_user_input=async_validate_cover,
    ),
    "cover_output2": SchemaFlowFormStep(
        schema=create_io_output_two_way_output2_schema(),
        validate_user_input=async_validate_cover,
    ),
    "event": SchemaFlowFormStep(
        schema=create_io_input_schema(
            {
                vol.Optional(
                    CONF_DEVICE_CLASS, default=EventDeviceClass.BUTTON
                ): create_list_selector(list(EventDeviceClass))
            }
        ),
        validate_user_input=async_validate_event,
    ),
    "light": SchemaFlowFormStep(
        schema=create_io_output_schema(pwm=True),
        validate_user_input=async_validate_light,
    ),
    "sensor": SchemaFlowFormStep(
        schema=vol.Schema(
            {
                vol.Required(CONF_ADDRESS): SELECTOR_ADDRESS,
                vol.Required(CONF_1W_PORT): SELECTOR_1W_PORT,
            }
        ),
        validate_user_input=async_validate_sensor,
    ),
    "siren": SchemaFlowFormStep(
        schema=create_io_output_schema(pwm=True),
        validate_user_input=async_validate_siren,
    ),
    "switch": SchemaFlowFormStep(
        schema=create_io_output_schema(), validate_user_input=async_validate_switch
    ),
    "valve": SchemaFlowFormStep(
        schema=create_io_output_two_way_select_schema(list(ValveDeviceClass)),
        next_step=create_two_way_next_step("valve"),
    ),
    "valve_output1": SchemaFlowFormStep(
        schema=create_io_output_two_way_output1_schema(),
        validate_user_input=async_validate_valve,
    ),
    "valve_output2": SchemaFlowFormStep(
        schema=create_io_output_two_way_output2_schema(),
        validate_user_input=async_validate_valve,
    ),
}


class BmhConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Bali Művek Home Controller."""

    config_flow = CONFIG_FLOW

    @staticmethod
    def get_io_output_pwm_string(address: int, options: Mapping[str, Any]) -> str:
        """Get configuration entry title for PWM capable I/O outputs."""

        output_string = Strings.get_io_output(address, options[CONF_IO_OUTPUT])

        if options[CONF_PWM]:
            return f"{output_string}; PWM"

        return output_string

    @staticmethod
    def get_two_way_string(address: int, options: Mapping[str, Any]) -> str:
        """Get configuration entry title for two way I/O outputs."""

        output = options[CONF_IO_OUTPUT]

        match options[CONF_TWO_WAY_OUTPUT_TYPE]:
            case TwoWayOutputType.NORMALLY_CLOSED:
                return f"{Strings.get_io_input(address, output)}; NC"
            case TwoWayOutputType.NORMALLY_OPENED:
                return f"{Strings.get_io_input(address, output)}; NO"
            case TwoWayOutputType.PWM:
                return f"{Strings.get_io_input(address, output)}; PWM"
            case TwoWayOutputType.TWO_DIRECTION:
                return (
                    f"IO Output[{Strings.get_address_port(address, output)}, "
                    f"{Strings.get_address_port(options[CONF_ADDRESS2], options[CONF_IO_OUTPUT2])}]; TwoWay"
                )
            case _ as output_type:
                raise ValueError(f"Unknown two way output type '{output_type}'.")

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Get configuration entry title."""

        platform = options[CONF_PLATFORM]
        address = options[CONF_ADDRESS]

        match platform:
            case Platform.BINARY_SENSOR | Platform.EVENT:
                resource = Strings.get_io_input(address, options[CONF_IO_INPUT])
            case Platform.COVER | Platform.VALVE:
                resource = self.get_two_way_string(address, options)
            case Platform.LIGHT | Platform.SIREN:
                resource = self.get_io_output_pwm_string(address, options)
            case Platform.SWITCH:
                resource = Strings.get_io_output(address, options[CONF_IO_OUTPUT])
            case Platform.SENSOR:
                resource = Strings.get_1w_port(address, options[CONF_1W_PORT])
            case _:
                raise ValueError(f"Unknown platform '{platform}'.")

        platform_str = platform.replace("_", " ").capitalize()

        return f"{platform_str}: {resource}"
