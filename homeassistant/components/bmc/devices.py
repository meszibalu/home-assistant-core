"""BMC device helper."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.bmc import BmcHub
from homeassistant.components.bmc.const import CONF_ADDRESS, CONF_IO_OUTPUT, CONF_PWM, CONF_1W_PORT, CONF_INVERT, \
    CONF_IO_INPUT, CONF_DEVICE_CLASS, CONF_TIMEOUT2, CONF_ADDRESS2, CONF_IO_OUTPUT2, CONF_INVERT2, CONF_TIMEOUT
from homeassistant.components.bmc.two_way_output import TwoWayOutputType
from homeassistant.components.event import EventDeviceClass
from homeassistant.core import HomeAssistant

class Devices:
    @staticmethod
    def get_address_string(address: int) -> str:
        return "0x%03X" % address

    @staticmethod
    def get_address_port_string(address: int, input: int) -> str:
        return f"{Devices.get_address_string(address)}/{input}"

    @staticmethod
    def get_io_input_string(address: int, input: int) -> str:
        return f"IO Input={Devices.get_address_port_string(address, input)}"

    @staticmethod
    def get_io_output_string(address: int, output: int) -> str:
        return f"IO Output={Devices.get_address_port_string(address, output)}"

    @staticmethod
    def get_1w_port_string(address: int, port: int) -> str:
        return f"1W Port={Devices.get_address_port_string(address, port)}"

    @staticmethod
    def get_unique_id(address: int, *args: any) -> str:
        parts = ["%03X" % address, *args]
        return ".".join(map(str, parts))

    @staticmethod
    def parse_address(options: dict[str, any], key: str = CONF_ADDRESS) -> int:
        if key not in options:
            raise ValueError("Missing address.")

        address = str(options[key])

        if len(address) != 3:
            raise ValueError(f"Invalid address '0x{address}'. It must be 0xBAA where B is the bus (0, 1) and "
                             f"AA is the device address (10 - 6F).")

        try:
            return int(address, 16)
        except ValueError:
            raise ValueError(f"Invalid address '0x{address}'. It must be 0xBAA where B is the bus (0, 1) and "
                             f"AA is the device address (10 - 6F).")

    @staticmethod
    def __get_used_error(resource: str) -> ValueError:
        return ValueError(f"Resource '{resource}' is already used by another entity.")

    @staticmethod
    def __get_io_input_used_error(address: int, input: int) -> ValueError:
        return Devices.__get_used_error(Devices.get_io_input_string(address, input))

    @staticmethod
    def __get_io_output_used_error(address: int, output: int) -> ValueError:
        return Devices.__get_used_error(Devices.get_io_output_string(address, output))

    @staticmethod
    def __get_1w_port_used_error(address: int, port: int) -> ValueError:
        return Devices.__get_used_error(Devices.get_1w_port_string(address, port))

    @staticmethod
    def __parse_io_input(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        address = Devices.parse_address(options)
        input = int(options[CONF_IO_INPUT])

        hub = BmcHub.get(hass)

        if not hub.is_io_input_available(address, input):
            raise Devices.__get_io_input_used_error(address, input)

        return {
            CONF_ADDRESS: address,
            CONF_IO_INPUT: input,
            CONF_INVERT: options.get(CONF_INVERT, False)
        }

    @staticmethod
    def __parse_io_output(hass: HomeAssistant, options: dict[str, any], pwm: bool, suffix: str = "") -> dict[str, any]:
        address = Devices.parse_address(options, CONF_ADDRESS + suffix)
        output = int(options[CONF_IO_OUTPUT + suffix])

        hub = BmcHub.get(hass)

        if not hub.is_io_output_available(address, output):
            raise Devices.__get_io_output_used_error(address, output)

        if pwm:
            pwm_options = {CONF_PWM + suffix: options.get(CONF_PWM + suffix, False)}
        else:
            pwm_options = {}

        return {
            CONF_ADDRESS + suffix: address,
            CONF_IO_OUTPUT + suffix: output,
            **pwm_options,
            CONF_INVERT + suffix: options.get(CONF_INVERT + suffix, False)
        }

    @staticmethod
    def __parse_io_output_two_way(
            hass: HomeAssistant, output_type: TwoWayOutputType, options: dict[str, any]
    ) -> dict[str, any]:
        parsed = Devices.__parse_io_output(hass, options, False, "")

        match output_type:
            case TwoWayOutputType.NORMALLY_OPEN | TwoWayOutputType.NORMALLY_CLOSED | TwoWayOutputType.PWM:
                parsed.update({
                    CONF_ADDRESS2: 0,
                    CONF_IO_OUTPUT2: 0,
                    CONF_INVERT2: 0,
                })
            case TwoWayOutputType.TWO_DIRECTION:
                parsed2 = Devices.__parse_io_output(hass, options, False, "2")

                if (parsed[CONF_ADDRESS] == parsed2[CONF_ADDRESS2] and
                        parsed[CONF_IO_OUTPUT] == parsed2[CONF_IO_OUTPUT2]):
                    raise ValueError("Open and close output is the same.")

                parsed.update(parsed2)

        parsed.update({
            CONF_TIMEOUT: float(options.get(CONF_TIMEOUT, 0)),
            CONF_TIMEOUT2: float(options.get(CONF_TIMEOUT2, 0))
        })

        return parsed

    @staticmethod
    def __parse_1w_port(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        address = Devices.parse_address(options)
        port = int(options[CONF_1W_PORT])

        hub = BmcHub.get(hass)

        if not hub.is_1w_port_available(address, port):
            raise Devices.__get_1w_port_used_error(address, port)

        return {
            CONF_ADDRESS: address,
            CONF_1W_PORT: port
        }

    @staticmethod
    def __parse_list(options: dict[str, any], key: str, values: list[str]):
        value = options.get(key)

        if value is not None and value not in values:
            raise ValueError(f"Unknown value '{value}'.")

        return {key: value}

    @staticmethod
    def parse_binary_sensor(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        parsed = Devices.__parse_io_input(hass, options)

        parsed.update(
            Devices.__parse_list(options, CONF_DEVICE_CLASS, list(BinarySensorDeviceClass))
        )

        return parsed

    @staticmethod
    def parse_cover(hass: HomeAssistant, output_type: TwoWayOutputType, options: dict[str, any]) -> dict[str, any]:
        return Devices.__parse_io_output_two_way(hass, output_type, options)

    @staticmethod
    def parse_event(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        parsed = Devices.__parse_io_input(hass, options)

        parsed.update(
            Devices.__parse_list(options, CONF_DEVICE_CLASS, list(EventDeviceClass))
        )

        return parsed

    @staticmethod
    def parse_light(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        return Devices.__parse_io_output(hass, options, True)

    @staticmethod
    def parse_sensor(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        return Devices.__parse_1w_port(hass, options)

    @staticmethod
    def parse_siren(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        return Devices.__parse_io_output(hass, options, True)

    @staticmethod
    def parse_switch(hass: HomeAssistant, options: dict[str, any]) -> dict[str, any]:
        return Devices.__parse_io_output(hass, options, False)

    @staticmethod
    def parse_valve(hass: HomeAssistant, output_type: TwoWayOutputType, options: dict[str, any]) -> dict[str, any]:
        return Devices.__parse_io_output_two_way(hass, output_type, options)