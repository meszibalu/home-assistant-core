"""Config flow for Bali Muvek Controller integration."""

from __future__ import annotations

import logging
from typing import Mapping, Coroutine, Callable

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM, Platform
from . import PLATFORMS
from .const import DOMAIN, CONF_PWM, CONF_ADDRESS, CONF_IO_OUTPUT, CONF_1W_PORT, CONF_INVERT, CONF_IO_INPUT, \
    CONF_DEVICE_CLASS, CONF_TWO_WAY_OUTPUT_TYPE, CONF_TIMEOUT, CONF_ADDRESS2, \
    CONF_IO_OUTPUT2
from .devices import Devices
from .two_way_output import TwoWayOutputType
from ..binary_sensor import BinarySensorDeviceClass
from ..cover import CoverDeviceClass
from ..event import EventDeviceClass
from ..valve import ValveDeviceClass
from ...helpers.schema_config_entry_flow import SchemaFlowFormStep, SchemaConfigFlowHandler, \
    SchemaCommonFlowHandler, SchemaFlowError
from ...helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode, TextSelector, NumberSelector, \
    NumberSelectorConfig, BooleanSelector, NumberSelectorMode, TextSelectorConfig, Selector

_LOGGER = logging.getLogger(__name__)

SELECTOR_ADDRESS = TextSelector(
    TextSelectorConfig(prefix="0x")
)
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
        values: list[str], mode: SelectSelectorMode = SelectSelectorMode.DROPDOWN, sort: bool = True
) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=values,
            mode=mode,
            sort=sort
        )
    )

def create_io_input_schema(extras: dict[vol.Marker, Selector[any]]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_ADDRESS): SELECTOR_ADDRESS,
        vol.Required(CONF_IO_INPUT): SELECTOR_IO_INPUT,
        vol.Optional(CONF_INVERT, default=False): BooleanSelector(),
        **extras
    })

def create_io_output_schema(
        extras: dict[vol.Marker, Selector[any]] = None, pwm: bool = False, suffix: str = ""
) -> vol.Schema:
    if extras is None:
        extras = {}

    if pwm:
        pwm_schema = {
            vol.Optional(CONF_PWM + suffix, default=False): BooleanSelector()
        }
    else:
        pwm_schema = {}

    return vol.Schema({
        vol.Required(CONF_ADDRESS + suffix): SELECTOR_ADDRESS,
        vol.Required(CONF_IO_OUTPUT + suffix): SELECTOR_IO_OUTPUT,
        **pwm_schema,
        vol.Optional(CONF_INVERT + suffix, default=False): BooleanSelector(),
        **extras
    })

def create_io_output_two_way_select_schema(device_classes: list[str]) -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_DEVICE_CLASS): create_list_selector(device_classes),
        vol.Required(CONF_TWO_WAY_OUTPUT_TYPE): create_list_selector(list(TwoWayOutputType), sort=False)
    })

def create_io_output_two_way_output1_schema() -> vol.Schema:
    return create_io_output_schema({
        vol.Required(CONF_TIMEOUT): SELECTOR_TIMEOUT,
        vol.Required(CONF_TIMEOUT + "2"): SELECTOR_TIMEOUT
    })

def create_io_output_two_way_output2_schema() -> vol.Schema:
    output = create_io_output_schema({
        vol.Required(CONF_TIMEOUT): SELECTOR_TIMEOUT
    })
    output2 = create_io_output_schema({
        vol.Required(CONF_TIMEOUT + "2"): SELECTOR_TIMEOUT
    }, suffix="2")

    return output.extend(output2.schema)

async def get_next_step(user_input: dict[str, any]) -> str:
    return user_input[CONF_PLATFORM]

def create_two_way_next_step(platform: str) -> Callable[[dict[str, any]], Coroutine[any, any, str]]:
    async def get_two_way_next_step(user_input: dict[str, any]) -> str:
        output_type = TwoWayOutputType(user_input[CONF_TWO_WAY_OUTPUT_TYPE])

        match output_type:
            case TwoWayOutputType.NORMALLY_OPEN | TwoWayOutputType.NORMALLY_CLOSED | TwoWayOutputType.PWM:
                return f"{platform}_output1"
            case TwoWayOutputType.TWO_DIRECTION:
                return f"{platform}_output2"
            case _:
                raise ValueError(f"Unknown output type '{output_type}'.")

    return get_two_way_next_step

async def validate_binary_sensor(
        handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_binary_sensor(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(e)

async def validate_cover(
    handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_cover(handler.parent_handler.hass,
                                   handler.options[CONF_TWO_WAY_OUTPUT_TYPE], user_input)
    except ValueError as e:
        raise SchemaFlowError(e)

async def validate_event(
        handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_event(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(e)

async def validate_light(
        handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_light(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(e)

async def validate_sensor(
        handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_sensor(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(e)

async def validate_siren(
        handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_siren(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(e)

async def validate_switch(
        handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_switch(handler.parent_handler.hass, user_input)
    except ValueError as e:
        raise SchemaFlowError(e)

async def validate_valve(
    handler: SchemaCommonFlowHandler, user_input: dict[str, any]) -> dict[str, any]:
    try:
        return Devices.parse_valve(handler.parent_handler.hass,
                                   handler.options[CONF_TWO_WAY_OUTPUT_TYPE], user_input)
    except ValueError as e:
        raise SchemaFlowError(e)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=vol.Schema({
            vol.Required(CONF_PLATFORM): create_list_selector(PLATFORMS, mode=SelectSelectorMode.LIST)
        }),
        next_step=get_next_step
    ),
    "binary_sensor": SchemaFlowFormStep(
        schema=create_io_input_schema({
            vol.Optional(CONF_DEVICE_CLASS): create_list_selector(list(BinarySensorDeviceClass))
        }),
        validate_user_input=validate_binary_sensor
    ),
    "cover": SchemaFlowFormStep(
        schema=create_io_output_two_way_select_schema(list(CoverDeviceClass)),
        next_step=create_two_way_next_step("cover")
    ),
    "cover_output1": SchemaFlowFormStep(
        schema=create_io_output_two_way_output1_schema(),
        validate_user_input=validate_cover
    ),
    "cover_output2": SchemaFlowFormStep(
        schema=create_io_output_two_way_output2_schema(),
        validate_user_input=validate_cover,
    ),
    "event": SchemaFlowFormStep(
        schema=create_io_input_schema({
            vol.Optional(CONF_DEVICE_CLASS, default=EventDeviceClass.BUTTON): create_list_selector(list(EventDeviceClass))
        }),
        validate_user_input=validate_event
    ),
    "light": SchemaFlowFormStep(
        schema=create_io_output_schema(pwm=True),
        validate_user_input=validate_light
    ),
    "sensor": SchemaFlowFormStep(
        schema=vol.Schema({
            vol.Required(CONF_ADDRESS): SELECTOR_ADDRESS,
            vol.Required(CONF_1W_PORT): SELECTOR_1W_PORT
        }),
        validate_user_input=validate_sensor
    ),
    "siren": SchemaFlowFormStep(
        schema=create_io_output_schema(pwm=True),
        validate_user_input=validate_siren
    ),
    "switch": SchemaFlowFormStep(
        schema=create_io_output_schema(),
        validate_user_input=validate_switch
    ),
    "valve": SchemaFlowFormStep(
        schema=create_io_output_two_way_select_schema(list(ValveDeviceClass)),
        next_step=create_two_way_next_step("valve")
    ),
    "valve_output1": SchemaFlowFormStep(
        schema=create_io_output_two_way_output1_schema(),
        validate_user_input=validate_valve
    ),
    "valve_output2": SchemaFlowFormStep(
        schema=create_io_output_two_way_output2_schema(),
        validate_user_input=validate_valve
    ),
}

class BmcConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Bali Muvek Controller."""

    config_flow = CONFIG_FLOW

    @staticmethod
    def get_io_output_pwm_string(address: int, options: Mapping[str, any]) -> str:
        output_string = Devices.get_io_output_string(address, options[CONF_IO_OUTPUT])

        if options[CONF_PWM]:
            return f"{output_string}; PWM"
        else:
            return output_string

    @staticmethod
    def get_two_way_string(address: int, options: Mapping[str, any]) -> str:
        output = options[CONF_IO_OUTPUT]

        match options[CONF_TWO_WAY_OUTPUT_TYPE]:
            case TwoWayOutputType.NORMALLY_OPEN:
                return f"{Devices.get_io_input_string(address, output)}; NO"
            case TwoWayOutputType.NORMALLY_CLOSED:
                return f"{Devices.get_io_input_string(address, output)}; NC"
            case TwoWayOutputType.PWM:
                return f"{Devices.get_io_input_string(address, output)}; PWM"
            case TwoWayOutputType.TWO_DIRECTION:
                return (f"IO Output=[{Devices.get_address_port_string(address, output)}, "
                        f"{Devices.get_address_port_string(options[CONF_ADDRESS2], options[CONF_IO_OUTPUT2])}]; TwoWay")
            case _ as output_type:
                raise ValueError(f"Unknown two way output type '{output_type}'.")

    def async_config_entry_title(self, options: Mapping[str, any]) -> str:
        """Return config entry title."""
        platform = options[CONF_PLATFORM]
        address = options[CONF_ADDRESS]

        match platform:
            case Platform.BINARY_SENSOR | Platform.EVENT:
                resource = Devices.get_io_input_string(address, options[CONF_IO_INPUT])
            case Platform.COVER | Platform.VALVE:
                resource = self.get_two_way_string(address, options)
            case Platform.LIGHT | Platform.SIREN:
                resource = self.get_io_output_pwm_string(address, options)
            case Platform.SWITCH:
                resource = Devices.get_io_output_string(address, options[CONF_IO_OUTPUT])
            case Platform.SENSOR:
                resource = Devices.get_1w_port_string(address, options[CONF_1W_PORT])
            case _:
                raise ValueError(f"Unknown platform '{platform}'.")

        platform_str = platform.replace("_", " ").capitalize()

        return f"{platform_str}: {resource}"
